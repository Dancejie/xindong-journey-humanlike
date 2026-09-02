#!/usr/bin/env python3
"""Generate validated, protagonist-specific Day 1 copy without delaying run start."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agent_prompt import extract_json
from backend.day1_script import (
    _validate_introduction_choice,
    _validate_surface_text,
    build_day1_script_messages,
    validate_day1_node_script,
    validate_day1_script,
)
from backend.game_content import CARD_PACKAGE, CHARACTER_CARDS, CHARACTER_MAP, NODES, active_cast_ids, build_fallback_script_flavor, create_snapshot, utc_now
from backend.llm_provider import call_text, provider_config
from scripts.llm_env import load_local_llm_env


def repair_surface_fields(snapshot: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Replace only rejected surface fields; engine IDs/targets still come from the validated skeleton."""
    perspective_id = snapshot["player"]["perspectiveCharacterId"]
    cast_ids = active_cast_ids(snapshot)
    fallback = build_fallback_script_flavor(perspective_id, cast_ids)["nodes"]
    raw_nodes = payload.get("nodes") if isinstance(payload.get("nodes"), dict) else {}
    repaired_nodes: dict[str, Any] = {}
    repairs: list[str] = []
    for node_id, blueprint in NODES.items():
        raw = deepcopy(raw_nodes.get(node_id)) if isinstance(raw_nodes.get(node_id), dict) else {}
        safe = deepcopy(fallback[node_id])
        for field, minimum, maximum in (("title", 4, 36), ("text", 30, 180), ("action", 4, 80)):
            try:
                safe[field] = _validate_surface_text(raw.get(field), f"{node_id}.{field}", minimum, maximum)
            except ValueError:
                repairs.append(f"{node_id}.{field}")
        speaker_id = str(raw.get("speakerId") or "").strip()
        if speaker_id in {"narrator", "program", *(character_id for character_id in cast_ids if character_id != perspective_id)}:
            safe["speakerId"] = speaker_id
        else:
            repairs.append(f"{node_id}.speakerId")
        raw_by_id = {
            str(item.get("id")): item for item in raw.get("choices", [])
            if isinstance(item, dict) and item.get("id")
        }
        safe_by_id = {item["id"]: item for item in safe.get("choices", [])}
        for choice in blueprint.get("choices", []):
            choice_id = choice["id"]
            candidate = raw_by_id.get(choice_id, {})
            target = safe_by_id[choice_id]
            label_max = 120 if node_id == "introductions" else 42
            try:
                label = _validate_surface_text(candidate.get("label"), f"{node_id}.{choice_id}.label", 6, label_max)
                if node_id == "introductions":
                    _validate_introduction_choice(perspective_id, choice_id, label)
                target["label"] = label
            except ValueError:
                repairs.append(f"{node_id}.{choice_id}.label")
            try:
                target["hint"] = _validate_surface_text(candidate.get("hint"), f"{node_id}.{choice_id}.hint", 6, 52)
            except ValueError:
                repairs.append(f"{node_id}.{choice_id}.hint")
            if node_id in {"cast-first-impressions", "icebreaker-choice"}:
                target_id = candidate.get("targetCharacterId")
                if target_id in cast_ids and target_id != perspective_id:
                    target["targetCharacterId"] = target_id
                else:
                    repairs.append(f"{node_id}.{choice_id}.targetCharacterId")
            else:
                target["targetCharacterId"] = None
        if node_id in {"cast-first-impressions", "icebreaker-choice"}:
            targets = [item["targetCharacterId"] for item in safe["choices"]]
            if len(set(targets)) != 3:
                safe["choices"] = deepcopy(fallback[node_id]["choices"])
                repairs.append(f"{node_id}.targets")
        try:
            repaired_nodes[node_id] = validate_day1_node_script(snapshot, node_id, {"node": safe})
        except ValueError:
            repaired_nodes[node_id] = deepcopy(fallback[node_id])
            repairs.append(f"{node_id}.wholeNode")
    return {"nodes": repaired_nodes}, sorted(set(repairs))


async def generate_one(character_id: str, semaphore: asyncio.Semaphore) -> tuple[str, dict[str, Any]]:
    snapshot = create_snapshot(CHARACTER_MAP[character_id]["mbti"], character_id)
    messages = build_day1_script_messages(snapshot)
    last_error: Exception | None = None
    async with semaphore:
        card = next(card for card in CHARACTER_CARDS if card["id"] == character_id)
        for attempt in range(3):
            try:
                raw = (await call_text(messages, max_tokens=6000)).text
                payload = extract_json(raw)
                payload, repairs = repair_surface_fields(snapshot, payload)
                flavor = validate_day1_script(snapshot, payload)
                return character_id, {
                    "generatedAt": flavor["generatedAt"],
                    "payload": {"nodes": flavor["nodes"]},
                    "deterministicSurfaceRepairs": repairs,
                }
            except Exception as error:  # provider, JSON and contract failures share one bounded repair
                last_error = error
                if attempt < 2:
                    messages = [
                        *messages,
                        {
                            "role": "user",
                            "content": (
                                f"上一稿未通过确定性台本合同：{error}。请从头输出完整 JSON。"
                                f"尤其注意 introductions 三条 label 每条都必须逐字包含姓名“{card['names']['primary']}”和 MBTI“{card['mbti']}”，并包含公开背景和参加来意。"
                                "逐项核对八个 nodeId、speakerId 英文枚举、所有 choice id、非主角目标、长度和人物口吻；不要解释。"
                            ),
                        },
                    ]
        raise RuntimeError(f"{character_id} 三次生成均未通过：{last_error}")


async def polish_one(character_id: str, original: dict[str, Any], semaphore: asyncio.Semaphore) -> tuple[str, dict[str, Any]]:
    snapshot = create_snapshot(CHARACTER_MAP[character_id]["mbti"], character_id)
    messages = [
        *build_day1_script_messages(snapshot),
        {"role": "assistant", "content": json.dumps(original, ensure_ascii=False)},
        {
            "role": "user",
            "content": """现在做人物风味终审。上一稿结构可用，但还不够像当前主角本人，请从头输出完整 JSON：
1. title/text/action 一律用“你”承接主角，绝不把主角姓名写成第三人称；选项里的第一人称自我介绍可以说自己的名字。
2. 三个选项必须像主角此刻真的会说或做的话，至少一个体现其独有兴趣、观察或 preferredMoves，另外两个也遵循 sentenceShape；换成别的角色仍成立的泛化项目管理话术必须重写。
3. 不得编造骨架或人物卡未提供的食材、饮品、衣着、故障、钥匙等具体道具，也不要声称另一位嘉宾刚做过未提供的动作；只写可见的通用空间与动作。
4. introductions 的三条 label 都必须是可直接说出口的完整真人自我介绍，每条都清楚包含姓名、MBTI、人物卡确认的公开工作或日常背景、参加来意。三条分别写镜头前完整版、客厅简短版加一个人人能回答的问题、公开信息加有依据的反差来意；不得用紧张、秘密、谜语或抽象试探代替信息。
5. 人物卡 occupation 未确认时绝不编造职业，使用人物卡已有的日常背景：姜米说声音日记/录音/故事，陈叙说修旧相机。
6. 全文删除“看清一个人、赢任务、观察还是相信、说出自己的需要、建立信任、推进剧情、完成主线”等机械话；不写元话语、自相矛盾动作、后台目的或策略总结；hint 只说当下可感知的取舍。
保留所有 nodeId、choice id、targetCharacterId 和 speakerId 合同，只输出完整 JSON。""",
        },
    ]
    last_error: Exception | None = None
    async with semaphore:
        card = next(card for card in CHARACTER_CARDS if card["id"] == character_id)
        for attempt in range(3):
            try:
                raw = (await call_text(messages, max_tokens=6000)).text
                payload = extract_json(raw)
                payload, repairs = repair_surface_fields(snapshot, payload)
                flavor = validate_day1_script(snapshot, payload)
                return character_id, {
                    "generatedAt": flavor["generatedAt"],
                    "payload": {"nodes": flavor["nodes"]},
                    "deterministicSurfaceRepairs": repairs,
                }
            except Exception as error:
                last_error = error
                if attempt < 2:
                    messages.append({"role": "user", "content": (
                        f"终审仍未通过：{error}。请修复并重新输出八节点完整 JSON，不要解释。"
                        f"introductions 三条 label 每条都必须逐字包含姓名“{card['names']['primary']}”和 MBTI“{card['mbti']}”，并包含人物卡确认的公开背景与参加来意；不能只改其中一条。"
                    )})
        raise RuntimeError(f"{character_id} 三次人物风味终审均未通过：{last_error}")


async def generate_cache(concurrency: int, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    config = provider_config()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    character_ids = [card["id"] for card in CHARACTER_CARDS]
    if existing is None:
        results = await asyncio.gather(*(generate_one(character_id, semaphore) for character_id in character_ids))
    else:
        results = await asyncio.gather(*(
            polish_one(character_id, existing["flavors"][character_id]["payload"], semaphore)
            for character_id in character_ids
        ))
    generated_at = utc_now()
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "characterCardContentVersion": CARD_PACKAGE["contentVersion"],
        "generator": config.provenance,
        "flavors": dict(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "content" / "day1_script_flavors.v1.json")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--polish-existing", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--provider", choices=("deepseek", "dots"))
    args = parser.parse_args()
    try:
        load_local_llm_env(ROOT, args.env_file)
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from error
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    try:
        provider_config()
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    existing = None
    if args.polish_existing:
        existing = json.loads(args.output.read_text(encoding="utf-8"))
    package = asyncio.run(generate_cache(args.concurrency, existing))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "output": str(args.output),
        "flavorCount": len(package["flavors"]),
        "provider": package["generator"]["provider"],
        "model": package["generator"]["model"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
