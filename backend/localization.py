"""Authored English presentation, with stable engine identifiers and raw memories."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from functools import lru_cache
from typing import Any

LOCALE_ROOT = Path(__file__).resolve().parent.parent / "content" / "locales"


def normalize_language(value: Any) -> str:
    return "en" if str(value or "").lower().split("-")[0] == "en" else "zh-CN"


@lru_cache(maxsize=1)
def english_copy() -> dict[str, str]:
    copy: dict[str, str] = {}
    for path in sorted(LOCALE_ROOT.glob("en-*.json")):
        copy.update(json.loads(path.read_text(encoding="utf-8")))
    return copy


def character_name(card_or_id: Any, language: str = "en") -> str:
    if isinstance(card_or_id, dict):
        name = card_or_id.get("names", {}).get("primary") or card_or_id.get("name") or card_or_id.get("id", "")
        if card_or_id.get("isCustom"):
            return str(name)
    else:
        # Delayed import keeps this module usable while game_content initializes.
        from .game_content import CHARACTER_CARD_MAP
        card = CHARACTER_CARD_MAP.get(str(card_or_id), {})
        name = card.get("names", {}).get("primary", str(card_or_id))
        if card.get("isCustom"):
            return str(name)
    return translate_text(str(name)) if normalize_language(language) == "en" else str(name)


def translate_text(text: str) -> str:
    copy = english_copy()
    if text in copy:
        return copy[text]
    # These templates contain real names or verbatim memory excerpts. Translate
    # the authored envelope while retaining the quoted original evidence.
    patterns = (
        (r"选客厅卡，去问(.+)刚才没展开的参加原因", lambda m: f"Pick the living-room card: ask {translate_text(m[1])} more about why they joined."),
        (r"选露台卡，和(.+)交换这七天最想体验的事", lambda m: f"Pick the terrace card: ask {translate_text(m[1])} what they want to try this week."),
        (r"选行李区卡，先问(.+)要不要搭把手放行李", lambda m: f"Pick the luggage-area card: ask {translate_text(m[1])} if they could use a hand."),
        (r"先和(.+)从一句你好开始", lambda m: f"Start with a hello to {translate_text(m[1])}"),
        (r"(.+)正在等你开口。先交换姓名和来到节目的原因；完成一次自然寒暄后，再决定要不要一起准备今晚的晚餐。", lambda m: f"{translate_text(m[1])} is waiting to hear from you. Exchange names and talk about why you joined. After a real conversation, decide whether to prepare dinner together."),
        (r"把今晚的短信发给 (.+)", lambda m: f"Send tonight's message to {translate_text(m[1])}"),
        (r"(.+) · 今天的态度：(.+)", lambda m: f"{m[1]} · Mood today: {m[2]}"),
        (r"今天和你聊到“(.+)”，我还想继续听你说下去。", lambda m: f"When we talked about “{m[1]}” today, I wanted to hear more."),
        (r"和你相处比想象中轻松。明天见到(.+)，我想先说声早。", lambda m: f"Being with you felt easier than I expected. I'd like to say good morning to {translate_text(m[1])} tomorrow."),
        (r"你今天说到“(.+)”时，我很想再听你讲一点。明天见。", lambda m: f"When you mentioned “{m[1]}” today, I wanted to hear more. See you tomorrow."),
        (r"昨晚的短信没有署名，但(.+)仍记得你们聊过的那件小事。今天，彼此有了继续认识的机会。", lambda m: f"Last night's message was anonymous, but {translate_text(m[1])} still remembers the small thing you talked about. Today brings another chance to get to know each other."),
        (r"(.+)没有停在昨夜", lambda m: f"{translate_text(m[1])} carries into the morning"),
        (r"(.+)按昨夜记住的“(.+)”作出了今天的行动。(.*)", lambda m: f"{translate_text(m[1])} acts on what they remember: “{m[2]}”. {translate_text(m[3])}"),
        (r"节目组正在引导你先和(.+)完成第一次破冰交流", lambda m: f"First, complete your icebreaker conversation with {translate_text(m[1])}."),
        (r"(.+)现在不在(.+)", lambda m: f"{translate_text(m[1])} is not at {translate_text(m[2])} right now."),
        (r"(?:模型角色|群聊角色)输出未通过人物卡校验：(.*)", lambda m: "The reply didn't match the character or current scene. This turn wasn't saved. Please try again."),
        (r"模型剧情导演输出未通过事件合同：(.*)", lambda m: "The next event couldn't be validated. Your story hasn't advanced. Please try again."),
        (r"模型角色判断暂时没有完成（([^）]+)），请重试这句话", lambda m: f"The dialogue model couldn't finish ({m[1]}). This turn wasn't saved. Please try again."),
        (r"模型剧情导演暂时没有完成判断（([^）]+)），请重试", lambda m: f"The story director couldn't finish ({m[1]}). Your story hasn't advanced. Please try again."),
        (r"(.+)的群聊回复暂时没有完成；本轮未写入任何记忆", lambda m: f"{translate_text(m[1])}'s group reply wasn't completed. No memories were saved this turn."),
        (r"(.+) 内容过长或包含不可识别字符", lambda m: "One of the profile fields is too long or contains unsupported characters. Please shorten it and try again."),
        (r"本次未提交视频：(.*)。人物卡已保存，可以先用照片游玩。", lambda m: f"No video was submitted: {translate_text(m[1])}. Your character is saved; you can play with your photo."),
        (r"视频未达到 (.+) 秒、480p 竖屏 H.264 的约定规格。", lambda m: f"The video doesn't meet the agreed {m[1]}-second, 480p portrait H.264 specification."),
    )
    for pattern, render in patterns:
        match = re.fullmatch(pattern, text, flags=re.S)
        if match:
            return render(match)
    # Exact sentence fragments cover script beats split from authored paragraphs.
    if any(separator in text for separator in ("。", "；", "、")):
        pieces = re.split(r"(?<=[。；])|、", text)
        translated = [copy.get(piece, copy.get(piece.rstrip("。；"), piece)) for piece in pieces if piece]
        if all(not re.search(r"[\u4e00-\u9fff]", piece) for piece in translated):
            return " ".join(translated)
    return text


# Immutable semantic enums and exact player evidence must survive presentation
# localization: they are read again by the engine and its privacy contracts.
_RAW_FIELDS = {"playerText", "playerInput", "rawQuote", "agentReply", "customText", "input", "gender", "pronouns", "id", "runId", "nodeId", "characterId", "targetCharacterId", "perspectiveCharacterId", "intentId", "source", "src", "path", "portrait", "video", "url", "publicReasonCode"}


def localize(value: Any, language: str, *, _key: str | None = None) -> Any:
    if normalize_language(language) != "en":
        return deepcopy(value)
    if _key == "userProfile":
        return deepcopy(value)
    if isinstance(value, dict):
        result = {key: localize(item, language, _key=key) for key, item in value.items()}
        identity_id = str(value.get("id") or value.get("characterId") or value.get("perspectiveCharacterId") or "")
        if identity_id.startswith("custom-"):
            for key in ("name", "displayName", "characterName"):
                if key in value:
                    result[key] = deepcopy(value[key])
        if str(value.get("playerCharacterId") or "").startswith("custom-") and "playerCharacterName" in value:
            result["playerCharacterName"] = value["playerCharacterName"]
        if isinstance(value.get("participantIds"), list) and isinstance(value.get("participantNames"), list):
            for index, participant_id in enumerate(value["participantIds"]):
                if str(participant_id).startswith("custom-") and index < len(value["participantNames"]):
                    result["participantNames"][index] = value["participantNames"][index]
        if value.get("isCustom"):
            # User-authored facts and names are data, even when they happen to
            # be identical to one of the library's Chinese dictionary entries.
            for key in ("name", "names", "userProfile", "customIntroduction"):
                if key in value:
                    result[key] = deepcopy(value[key])
            if isinstance(value.get("sourceProfile"), dict):
                for key in ("facts", "sourceName"):
                    if key in value["sourceProfile"]:
                        result["sourceProfile"][key] = deepcopy(value["sourceProfile"][key])
            occupation = value.get("occupation")
            if isinstance(occupation, str) and occupation not in {"职业待公开", "职业暂未公开"}:
                result["occupation"] = occupation
                if isinstance(result.get("publicFacts"), dict):
                    result["publicFacts"]["occupation"] = occupation
        if isinstance(value.get("text"), str) and isinstance(value.get("textBeats"), list) and re.search(r"[\u4e00-\u9fff]", value["text"]):
            translated_text = result.get("text", "")
            if translated_text and not re.search(r"[\u4e00-\u9fff]", translated_text):
                result["textBeats"] = english_beats(translated_text)
        return result
    if isinstance(value, list):
        return [localize(item, language, _key=_key) for item in value]
    if isinstance(value, tuple):
        return tuple(localize(item, language, _key=_key) for item in value)
    if isinstance(value, str) and _key not in _RAW_FIELDS:
        translated = translate_text(value)
        if _key == "detail" and re.search(r"[\u4e00-\u9fff]", translated):
            return "That action couldn't be completed. Please refresh and try again."
        return translated
    return deepcopy(value)


def english_beats(text: str) -> list[str]:
    """Keep English paragraphs readable without borrowing Chinese word limits."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    beats: list[str] = []
    for sentence in sentences:
        while len(sentence) > 235:
            cut = sentence.rfind(" ", 80, 235)
            cut = cut if cut > 0 else 235
            beats.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            if beats and len(beats[-1]) + len(sentence) + 1 <= 200:
                beats[-1] += " " + sentence
            else:
                beats.append(sentence)
    return beats
