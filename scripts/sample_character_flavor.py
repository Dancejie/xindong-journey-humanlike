#!/usr/bin/env python3
"""Call DeepSeek locally with every v3 card and produce a compact flavor report."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agent_prompt import build_agent_messages, extract_json  # noqa: E402
from backend.game_content import (  # noqa: E402
    CHARACTER_CARDS,
    active_cast_ids,
    create_snapshot,
    validate_agent_turn,
)


DEFAULT_INPUT = "我不想听节目里的标准答案。告诉我，你为什么还留在这里？如果现在只能做一件真事，你会做什么？"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


async def request_turn(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, card: dict, snapshot: dict, player_input: str, api_key: str, base_url: str, model: str) -> dict:
    async with semaphore:
        messages = build_agent_messages(card, snapshot, player_input)
        validated = None
        for attempt in range(2):
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": 760, "stream": False, "thinking": {"type": "disabled"}},
            )
            response.raise_for_status()
            choices = response.json().get("choices") or []
            raw = str(choices[0].get("message", {}).get("content") or "").strip() if choices else ""
            payload = extract_json(raw)
            try:
                validated = validate_agent_turn(card, payload, snapshot, player_input)
                break
            except Exception as error:
                if attempt == 1:
                    if any(term in str(error) for term in ("建议语", "followup", "mainline")):
                        payload.pop("suggestions", None)
                        validated = validate_agent_turn(card, payload, snapshot, player_input)
                        break
                    raise RuntimeError(
                        f"{card['names']['primary']} 连续两次未通过：{error}；"
                        f"末次台词={str(payload.get('dialogue') or '')[:260]}"
                    ) from error
                messages = [
                    *messages,
                    {"role": "user", "content": f"上一轮未通过人物与时间线合同：{error}。保持同一人物判断，重写完整 JSON；只使用当前已发生事实。"},
                ]
        assert validated is not None
        return {
            "characterId": card["id"], "name": card["names"]["primary"], "mbti": card["mbti"],
            **validated,
            "relationshipDelta": {
                axis: int(validated["relationshipDelta"].get(axis, 0))
                for axis in card["agentPolicy"]["deltaBounds"]
            },
            "activatedEventId": None,
        }


def markdown_report(results: list[dict], player_input: str, model: str) -> str:
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = [
        "# DeepSeek 人物对白风味样片（本地）",
        "",
        f"- 生成时间：{generated}",
        f"- 模型：`{model}`",
        "- 人物卡：`content/character_cards.v3.json`",
        f"- 同一玩家输入：{player_input}",
        "- 边界：本报告只验证角色表演、态度、记忆与受约束参数建议；不提交状态，也未写入线上数据库。",
        "",
        "## 横向速览",
        "",
        "| 人物 | MBTI | 态度 | 意图 | 事件提议 / 实际激活 |",
        "|---|---|---|---|---|",
    ]
    for item in results:
        proposed = "是" if item.get("proposedEventId") else "否"
        activated = "是" if item.get("activatedEventId") else "否"
        lines.append(f"| {item['name']} | {item['mbti']} | {item['attitude']} | {item['intentId']} | {proposed} / {activated} |")
    for item in results:
        delta = "、".join(f"{key} {value:+d}" for key, value in item["relationshipDelta"].items() if value) or "无"
        lines.extend([
            "",
            f"## {item['name']} · {item['mbti']}",
            "",
            f"> {item['stageDirection']} {item['dialogue']}",
            "",
            f"- 公开判断：{item['publicReason']}",
            f"- 参数建议：{delta}",
            f"- 写入候选记忆：{item['memory']['summary']}（角色解释：{item['memory']['interpretation']}）",
            f"- 事件建议 / 实际激活：{item.get('proposedEventId') or '无'} / {item.get('activatedEventId') or '无'}",
        ])
    lines.extend([
        "",
        "## 人工验收重点",
        "",
        "- 八个人是否能在不显示 MBTI 术语的情况下被区分。",
        "- 台词是否至少推进一个事实、动作、问题、反价或边界。",
        "- 零信任是否避免直接倾倒隐藏身世。",
        "- 参数是否克制，事件是否只在角色确实交出物件或邀约时提出。",
        "- 文学锚点是否只留下决策结构，没有出现原句复刻。",
        "",
    ])
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    env = {**load_env(Path(args.env_file)), **os.environ}
    api_key = env.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY 未配置")
    base_url = env.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    model = env.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    snapshot = create_snapshot(args.player_mbti, args.player_character or None)
    cards = [card for card in CHARACTER_CARDS if not args.character or card["id"] in args.character]
    active_ids = set(active_cast_ids(snapshot))
    player_id = snapshot["player"]["perspectiveCharacterId"]
    invalid = [card["id"] for card in cards if card["id"] == player_id or card["id"] not in active_ids]
    if invalid:
        raise SystemExit(
            "抽样角色必须在当前八人阵容且不能是玩家本人：" + ", ".join(invalid)
            + f"；当前玩家={player_id}，阵容={','.join(active_cast_ids(snapshot))}"
        )
    scene_snapshots: list[dict] = []
    for card in cards:
        scene_snapshot = deepcopy(snapshot)
        if args.scene_node:
            scene_snapshot["nodeId"] = args.scene_node
        scene_snapshot["sceneContext"] = {
            "version": 1,
            "time": "DAY 1 · 18:42",
            "locationId": "villa-living-room",
            "locationName": "别墅客厅",
            "channel": "1v1",
            "participantIds": [player_id, card["id"]],
            "participantNames": [
                next(item["names"]["primary"] for item in CHARACTER_CARDS if item["id"] == player_id),
                card["names"]["primary"],
            ],
        }
        if args.conversation_mode == "reopening":
            scene_snapshot["echoMemories"].append({
                "id": f"local-flavor-memory-{card['id']}",
                "characterId": card["id"],
                "kind": "episodic",
                "summary": f"集体自我介绍结束后，玩家记住了{card['names']['primary']}公开说过的来意",
                "interpretation": "玩家在听具体内容，但双方还没有形成亲密承诺",
                "rawQuote": "先从一件眼前的小事认识彼此",
                "agentReply": "先不把答案说满，我们从眼前这件事聊。",
                "attitude": "curious",
                "time": "DAY 1 · 18:30",
                "locationName": "别墅客厅",
                "channel": "group",
                "participantNames": ["八位嘉宾"],
            })
            scene_snapshot["agentConversations"][card["id"]] = {
                "turnCount": 1,
                "topicLedger": [{
                    "topic": "集体自我介绍与参加来意",
                    "time": "DAY 1 · 18:30",
                    "locationName": "别墅客厅",
                }],
            }
        if scene_snapshot["nodeId"] == "guided-chat":
            scene_snapshot["pendingInteraction"] = {
                "type": "guided-first-chat", "targetCharacterId": card["id"],
                "status": "required", "requiredTurnCount": 1, "completedTurnCount": 0,
                "sourceChoiceId": "local-flavor-qa", "reason": "本地人物风味验收",
            }
        scene_snapshots.append(scene_snapshot)
    semaphore = asyncio.Semaphore(max(1, min(args.concurrency, 2)))
    async with httpx.AsyncClient(timeout=90) as client:
        jobs = [
            request_turn(client, semaphore, card, scene_snapshot, args.player_input, api_key, base_url, model)
            for card, scene_snapshot in zip(cards, scene_snapshots)
        ]
        results = await asyncio.gather(*jobs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_report(results, args.player_input, model), encoding="utf-8")
    json_output = output.with_suffix(".json")
    json_output.write_text(json.dumps({"model": model, "playerInput": args.player_input, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(results)} validated turns -> {output}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(ROOT / ".env.deepseek.local"))
    parser.add_argument("--output", default=str(ROOT / "qa" / "DEEPSEEK-CHARACTER-FLAVOR.md"))
    parser.add_argument("--player-input", default=DEFAULT_INPUT)
    parser.add_argument("--player-mbti", default="INFP")
    parser.add_argument("--player-character")
    parser.add_argument("--scene-node", default="guided-chat")
    parser.add_argument("--conversation-mode", choices=("first-meeting", "reopening"), default="reopening")
    parser.add_argument("--character", action="append")
    parser.add_argument("--concurrency", type=int, default=2)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
