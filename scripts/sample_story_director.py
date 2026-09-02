#!/usr/bin/env python3
"""Run isolated story-director scenarios through the selected local LLM."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agent_prompt import extract_json  # noqa: E402
from backend.game_content import CHARACTER_MAP, active_cast_ids, create_snapshot  # noqa: E402
from backend.llm_provider import call_text, provider_config  # noqa: E402
from backend.story_director import (  # noqa: E402
    build_story_director_messages,
    commit_story_event,
    eligible_story_events,
    validate_story_director_output,
)
from scripts.llm_env import load_local_llm_env  # noqa: E402


def add_memory(snapshot: dict, character_id: str, index: int, *, valence: int = 25, interpretation: str = "对方愿意把判断变成下一步行动") -> None:
    snapshot["echoMemories"].append({
        "id": f"sample-{character_id}-{index}", "ownerId": character_id, "characterId": character_id,
        "kind": "episodic", "summary": f"玩家与{CHARACTER_MAP[character_id]['name']}完成了一次有具体问题和回应的交流",
        "interpretation": interpretation, "salience": 72, "emotionalValence": valence, "callbackEligible": True,
    })


def set_relationship(snapshot: dict, character_id: str, values: dict[str, int]) -> None:
    snapshot["relationships"][character_id].update(values)
    if "trust" in values:
        snapshot["trust"][character_id] = values["trust"]
    if "affection" in values:
        snapshot["affection"][character_id] = values["affection"]


def snapshot_with_cast(user_mbti: str, perspective_character_id: str, required_ids: set[str]) -> dict:
    """Build a disposable comparison snapshot whose randomized roster contains the scenario cast."""
    for _ in range(256):
        snapshot = create_snapshot(user_mbti, perspective_character_id)
        if required_ids.issubset(set(active_cast_ids(snapshot))):
            return snapshot
    raise RuntimeError(f"无法为剧情导演样片组出所需嘉宾：{sorted(required_ids)}")


def scenarios() -> list[tuple[str, str, dict]]:
    early = snapshot_with_cast("INFP", "jiangmi", {"shenmo", "jiangmi"})
    early["nodeId"] = "team-up"; early["storyArc"]["phase"] = "early"
    add_memory(early, "shenmo", 0); add_memory(early, "jiangmi", 0)
    set_relationship(early, "shenmo", {"trust": 2, "respect": 2, "attraction": 1})
    set_relationship(early, "jiangmi", {"trust": 1, "respect": 1, "attraction": 1})

    triangle = snapshot_with_cast("ENFP", "jiangmi", {"jiangmi", "shenmo", "chengye"})
    triangle["nodeId"] = "callback"; triangle["storyArc"]["phase"] = "middle"
    for index in range(2):
        add_memory(triangle, "shenmo", index, valence=30)
        add_memory(triangle, "chengye", index, valence=35)
    set_relationship(triangle, "shenmo", {"trust": 1, "affection": 2, "respect": 3, "attraction": 4})
    set_relationship(triangle, "chengye", {"trust": 1, "affection": 3, "respect": 1, "attraction": 5})
    triangle["attitudes"].update({"shenmo": "challenging", "chengye": "challenging"})
    triangle["storyEventLedger"] = [
        {"eventId": "story.identity.profession-reveal", "status": "completed"},
        {"eventId": "story.date.blind-box", "status": "completed"},
    ]

    late = snapshot_with_cast("INFJ", "shenmo", {"shenmo", "jiangwan", "linyu"})
    late["nodeId"] = "callback"; late["storyArc"]["phase"] = "late"
    for index in range(4):
        add_memory(late, "jiangwan", index, valence=35)
    for index in range(3):
        add_memory(late, "linyu", index, valence=20)
    set_relationship(late, "jiangwan", {"trust": 6, "affection": 5, "respect": 5, "attraction": 4})
    set_relationship(late, "linyu", {"trust": 4, "affection": 3, "respect": 4, "attraction": 2})
    late["attitudes"].update({"jiangwan": "honest", "linyu": "steady"})
    return [
        ("初期协作", "两位嘉宾都留下了具体交流证据，但还没有形成稳定选择。", early),
        ("中期双线拉扯", "职业公开和盲盒约会已经发生；玩家同时与沈墨、程野形成吸引，两人的关系证据明显不同。", triangle),
        ("后期现实选择", "告白前的最后旅行即将开始；玩家与江晚形成最稳定的信任，也保留着与林屿的长期照顾线。", late),
    ]


async def request_one(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, name: str, setup: str, snapshot: dict, provider: str) -> dict:
    candidates = eligible_story_events(snapshot, limit=8)
    if not candidates:
        raise RuntimeError(f"{name} 没有候选事件")
    messages = build_story_director_messages(snapshot, candidates)
    validated = None
    last_error = None
    for attempt in range(3):
        request_messages = messages if not last_error else [*messages, {"role": "user", "content": f"上一份 JSON 未通过事件合同：{last_error}。请重新输出完整 JSON；只写候选参与者的行动。"}]
        async with semaphore:
            raw = (await call_text(
                request_messages, max_tokens=1100, provider=provider, client=client,
            )).text
        try:
            validated = validate_story_director_output(snapshot, candidates, extract_json(raw))
            break
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            last_error = str(error)
    if validated is None:
        raise RuntimeError(f"{name} 连续三次未通过事件合同：{last_error}")
    next_snapshot, receipt = commit_story_event(snapshot, candidates, validated)
    return {
        "scenario": name, "setup": setup, "candidateIds": [item["eventId"] for item in candidates],
        "validated": validated, "receipt": receipt,
        "committedMission": next_snapshot.get("storyMission"),
    }


def markdown_report(results: list[dict], provider: str, model: str) -> str:
    provider_label = {"deepseek": "DeepSeek", "dots": "Dots"}[provider]
    lines = [
        f"# {provider_label} 剧情导演风味样片（本地）", "",
        f"- 生成时间：{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        f"- 供应商：`{provider}`",
        f"- 模型：`{model}`", "- 事件库：`content/story_event_catalog.v1.json`",
        "- 边界：三个场景均为隔离快照；只验证事件选择、桥段和主任务，不写入线上数据库。", "",
        "| 场景 | 决策 | 事件 | 参与者 |", "|---|---|---|---|",
    ]
    for result in results:
        item = result["validated"]
        names = "、".join(CHARACTER_MAP[cid]["name"] for cid in item["participantIds"]) or "无"
        lines.append(f"| {result['scenario']} | {item['decision']} | {item.get('proposedEventId') or '等待'} | {names} |")
    for result in results:
        item = result["validated"]
        lines.extend(["", f"## {result['scenario']}", "", f"- 局面：{result['setup']}", f"- 候选：{'、'.join(result['candidateIds'])}"])
        if item["decision"] == "activate":
            names = "、".join(CHARACTER_MAP[cid]["name"] for cid in item["participantIds"])
            lines.extend([f"- 激活：`{item['proposedEventId']}`（{names}）", f"- 桥段标题：{item['bridgeTitle']}", f"> {item['bridgeText']}", "", f"- 现场：{item['sceneSetup']}", f"- 反差：{item['reversalBeat']}", f"- 人物新理解：{item['characterInsight']}", f"- 动态画面：{item['visualCue']}", f"- 可用策略：{'；'.join(item['availableStrategies'])}", f"- 玩家主任务（事件库确定性合同）：{result['committedMission']['prompt']}", f"- 导演建议的执行切口：{item['playerMissionPrompt']}", f"- 公开原因：{item['publicReason']}"])
        else:
            lines.extend([f"- 等待原因：{item['bridgeText']}", f"- 下一步证据：{item['playerMissionPrompt']}"])
    lines.extend(["", "## 人工验收重点", "", "- 是否明确写清刚发生了什么、谁被卷入、玩家现在要做什么。", "- 是否真的根据三种关系局面选择了不同事件，而非泛化恋爱文案。", "- 是否只使用候选事件和合法参与者，没有新人物、新事实或状态补丁。", "- 是否保留拒绝、退出和隐私边界。", ""])
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    try:
        load_local_llm_env(ROOT, args.env_file)
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from error
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    try:
        config = provider_config()
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    semaphore = asyncio.Semaphore(2)
    async with httpx.AsyncClient(timeout=90) as client:
        results = await asyncio.gather(*[
            request_one(client, semaphore, name, setup, snapshot, config.name)
            for name, setup, snapshot in scenarios()
        ])
    output = Path(args.output) if args.output else ROOT / "qa" / f"{config.name.upper()}-STORY-DIRECTOR-FLAVOR.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_report(results, config.name, config.model), encoding="utf-8")
    output.with_suffix(".json").write_text(json.dumps({"provider": config.name, "model": config.model, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(results)} validated story-director scenarios -> {output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    parser.add_argument("--provider", choices=("deepseek", "dots"))
    parser.add_argument("--output")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
