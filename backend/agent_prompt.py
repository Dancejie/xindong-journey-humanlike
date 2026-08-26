"""Provider-neutral prompt assembly for bounded character performance."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


ATTITUDES = ["warm", "curious", "guarded", "challenging", "vulnerable", "softened", "uncertain", "honest", "moved", "careful", "steady", "boundary"]

HUMAN_SPEECH_CONTRACT = {
    "attention": "不要平均回应玩家的每个信息；只抓角色此刻真正注意到的一个具体词、动作或矛盾，其余内容可以暂时留白",
    "reactionOrder": "先产生角色自己的反应，再决定要不要解释、提问或行动；禁止先总结玩家、替玩家命名情绪",
    "incompleteness": "允许一句话没收满、一次自然改口或短暂停顿，但每轮最多一次；不要机械堆省略号、语气词和口头禅",
    "emotionalInertia": "上一轮的笑意、别扭、紧张、吃醋或防御不会因换话题立刻清零；重大态度变化必须有可见累积",
    "humor": "幽默只占本轮约三成以内，来自眼前观察、反差、误解或自嘲；说完即过，不解释笑点",
    "relationshipReason": "被问为什么参加或还留下时，先回答自己对人、关系或相处的真实选择；职业、爱好、道具和任务只能作生活细节，不能成为留在恋综的唯一理由",
    "sceneGrounding": "只使用当前 scene、recentMemories 与人物卡已确认的物件和事件；职业不能自动创造故障、工作任务、房间道具或幕后职责",
    "timeCoherence": "严格遵守 scene.time；不得出现今晚早餐、清晨晚餐或把尚未发生的明天写成当前事实",
    "antiAi": [
        "禁止换词复述玩家整句话",
        "禁止凭一句话分析出完整心理",
        "禁止每轮都完成回应、分析、建议、安慰、总结和邀请的闭环",
        "禁止客服式收尾、万能温柔和即时升华",
    ],
}

ROMANTIC_INTELLIGENCE_CONTRACT = {
    "definition": "恋商是准确接住对方的主动，同时保留双方主体性；不是油腻调情、照顾表演或心理咨询",
    "ordinaryTurn": "用一个具体细节表示在听，再给角色自己的感受、判断、轻巧反应或现场行动；不要只盘问对方",
    "affectionTurn": "遇到喜欢、心动或告白，先承认对方这次主动的具体分量，再清楚说自己的当下感受、边界或下一步；不把对方的喜欢当奖赏，不居高临下评价勇气，也不以自我贬低逼对方安慰",
    "agency": "女性角色的喜欢、拒绝、犹豫和改变主意都由她自己拥有；男性角色不得把自己写成拯救者、裁判或奖励发放者",
    "tension": "暧昧来自共同记忆、没完全说尽的选择和当下动作，不来自霸总话术、套路金句或突然定义关系",
    "responseSequence": "面对示好时依次做到：接住一个具体情绪或行为、给出自己的真实感受、必要时用一句低压力幽默卸力、把下一步选择留给双方；得到确认前不替关系命名或擅自靠近",
    "maleNpcShape": "男嘉宾优先使用‘接住情绪 + 一段具体共同记忆 + 轻微情境自嘲 + 可拒绝的行动邀请’，不能只问口味、连续盘问或抢着包办",
    "continuity": "用本轮的时间、地点、物件和共同记忆带来新内容；除非玩家主动新增事实，不绕回自我介绍、参加原因或开场喜好题",
    "questionBudget": "一轮最多一个问题；提问前必须先贡献角色自己的新信息、感受、边界或行动",
}


_SOURCE_TEXT_KEYS = {
    "microexcerpt", "sourceexcerpt", "sourcequote", "originalquote", "quote",
    "quotation", "rawexcerpt", "fulltext", "sourcetext", "passage",
    "originalline", "sourceurl",
}

_FEW_SHOT_CUE_LEXICONS = {
    "opening": ("初见", "第一次", "刚到", "入住", "自我介绍", "你好", "认识"),
    "support": ("支持", "不催", "理解", "帮", "陪", "照顾", "肯定", "相信"),
    "probe": ("为什么", "想知道", "追问", "问", "好奇", "解释"),
    "challenge": ("质疑", "挑战", "不信", "反对", "输赢", "证明", "争"),
    "boundary": ("拒绝", "边界", "不要", "不舒服", "越界", "逼迫", "强迫", "隐私", "授权", "替我决定"),
    "affection": ("喜欢", "心动", "告白", "在意", "暧昧", "约会", "短信"),
    "cooperation": ("一起", "分工", "厨房", "晚餐", "组队", "帮忙", "任务", "商量"),
    "repair": ("道歉", "说错", "误会", "修复", "重新", "补救"),
}


def _without_source_text(value: Any) -> Any:
    """Strip research quotations while preserving reviewed transfer rules."""
    if isinstance(value, dict):
        return {
            key: _without_source_text(item)
            for key, item in value.items()
            if key.lower().replace("_", "") not in _SOURCE_TEXT_KEYS
        }
    if isinstance(value, list):
        return [_without_source_text(item) for item in value]
    return value


def runtime_character_card(card: dict[str, Any]) -> dict[str, Any]:
    """Return the minimum character card safe for a runtime model prompt."""
    result = _without_source_text(deepcopy(card))
    for field in ("accent", "portrait", "video", "fewShots", "sourceRefIds"):
        result.pop(field, None)
    # Research provenance belongs to authoring/QA, not to the performance prompt.
    # The model receives only the reviewed, project-original behavior transfer.
    anchors = result.get("researchAnchors")
    if isinstance(anchors, list):
        result["researchAnchors"] = [
            {
                key: anchor[key]
                for key in ("observablePattern", "transferRule")
                if isinstance(anchor, dict) and anchor.get(key) not in (None, "")
            }
            for anchor in anchors
            if isinstance(anchor, dict)
        ]
    source_profile = result.get("sourceProfile")
    if isinstance(source_profile, dict):
        result["sourceProfile"] = {
            key: source_profile[key]
            for key in ("facts", "adaptationBoundary")
            if source_profile.get(key) not in (None, "")
        }
    facts = result.get("sourceProfile", {}).get("facts", {})
    occupation = facts.get("occupation")
    if isinstance(occupation, str) and any(term in occupation for term in ("待剧情", "待正式确认", "运行时职业待")):
        facts.pop("occupation", None)
    return result


def _cue_tags(text: str) -> list[str]:
    tags = []
    for cue, markers in _FEW_SHOT_CUE_LEXICONS.items():
        cue_text = text
        if cue == "affection":
            cue_text = cue_text.replace("不喜欢", "").replace("谈不上喜欢", "")
        if any(marker in cue_text for marker in markers):
            tags.append(cue)
    return tags


def _surface_tokens(text: str) -> set[str]:
    """Small deterministic lexical index; this is retrieval, not hidden CoT."""
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z0-9_-]{2,}", lowered))
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
        tokens.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return tokens


def _few_shot_structure(card: dict[str, Any], shot: dict[str, Any], index: int) -> dict[str, Any]:
    """Project either legacy or v4 few-shot data into one observable contract."""
    attitude = str(shot.get("attitude") or "curious")
    matrix_key = {
        "boundary": "boundaryViolation", "challenging": "challenging",
        "guarded": "probing", "curious": "probing",
    }.get(attitude, "supportive")
    reaction = card.get("reactionMatrix", {}).get(matrix_key, {})
    structure = {
        "id": str(shot.get("id") or f"fs.{card['id']}.runtime-{index + 1:02d}"),
        "situation": str(shot.get("situation") or shot.get("context") or "当前互动"),
        "playerMove": str(shot.get("playerMove") or shot.get("player") or shot.get("observableCue") or ""),
        "observableCue": str(shot.get("observableCue") or shot.get("playerMove") or shot.get("player") or ""),
        "publicInterpretation": str(shot.get("publicInterpretation") or reaction.get("internalShift") or "只判断眼前可见的行为，不替对方读心"),
        "chosenTactic": str(shot.get("chosenTactic") or reaction.get("speechMove") or "先给自己的反应，再推进一个具体动作"),
        "attitude": attitude,
        "stageDirection": str(shot.get("stageDirection") or ""),
        "dialogueExample": str(shot.get("dialogue") or shot.get("reply") or ""),
        "repairOrExit": str(shot.get("repairOrExit") or shot.get("repair") or "若现场反馈改变，就按人物卡边界修正或退出"),
        "copyBoundary": "只迁移决策顺序和句式力度；不得复刻示例措辞，不得模仿来源人物或作品",
    }
    return structure


def select_runtime_few_shots(
    card: dict[str, Any], message: str = "", scene: dict[str, Any] | None = None, limit: int = 3,
) -> dict[str, Any]:
    """Select 2-3 character-specific examples from observable message/scene cues."""
    scene = scene or {}
    scene_copy = " ".join(
        str(scene.get(key) or "")
        for key in ("nodeId", "storyStage", "conversationMode", "title", "sceneText", "locationName", "channel")
    )
    query = f"{message} {scene_copy}".strip()
    query_cues = _cue_tags(query)
    query_tokens = _surface_tokens(query)
    current_attitude = str(scene.get("currentAttitude") or "")
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, raw_shot in enumerate(card.get("fewShots") or []):
        if not isinstance(raw_shot, dict):
            continue
        shot_text = " ".join(
            str(raw_shot.get(key) or "")
            for key in (
                "situation", "context", "playerMove", "player", "observableCue",
                "publicInterpretation", "attitude",
            )
        )
        shot_cues = _cue_tags(shot_text)
        overlap = len(query_tokens & _surface_tokens(shot_text))
        score = overlap + 8 * len(set(query_cues) & set(shot_cues))
        if current_attitude and current_attitude == str(raw_shot.get("attitude") or ""):
            score += 3
        ranked.append((score, -index, _few_shot_structure(card, raw_shot, index)))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    requested = max(2, min(3, int(limit or 3)))
    selected = [item[2] for item in ranked[:requested]]
    return {
        "characterId": card["id"],
        "characterName": card.get("names", {}).get("primary"),
        "selectionBasis": {
            "nodeId": scene.get("nodeId"),
            "conversationMode": scene.get("conversationMode"),
            "observableCues": query_cues,
        },
        "usageRule": "只迁移这些原创微场景的可观察 cue→判断→策略→表达→修复结构；不得逐字复刻 dialogueExample，也不得调用或模仿研究来源原文",
        "items": selected,
    }

PUBLIC_CHAT_INTROS = {
    "shenmo": "我平时习惯等想清楚再开口，来这里是想试试答案还不完整时，也能不能诚实表达",
    "linyu": "我常常先照顾别人，来这里也想认识一个愿意问问我感受的人",
    "chengye": "我做事比说话快，这次想认真认识一个人，也认真完成一次约定",
    "guyan": "我习惯先拆问题再回答，来这里想试试不等到完美答案也能说真话",
    "jiangwan": "工作里常常听别人说，这次想放下分析，也让大家认识工作之外的我",
    "jiangmi": "我平时会录声音日记，来这里想看看和一个人安静待着时，能不能舒服地做自己",
    "sunnian": "我很会张罗大家的事，这次也想让别人认识不只是在帮忙的我",
    "chensu": "我喜欢修旧相机和坏掉的东西，这次想练习把该解释的话也说清楚",
}
PUBLIC_BACKGROUND_ANCHORS = {
    "shenmo": ("投行",), "linyu": ("建筑",), "chengye": ("极限运动", "品牌"),
    "guyan": ("游戏策划", "外包"), "jiangwan": ("心理咨询",),
    "jiangmi": ("声音日记", "录音"), "sunnian": ("插画",), "chensu": ("旧相机", "修"),
}
PUBLIC_REASON_ANCHORS = {
    "shenmo": ("感受", "慢一点", "认识", "真实"), "linyu": ("照顾", "感受", "被对待", "认识"),
    "chengye": ("认真", "认识", "约定", "陪一个人"), "guyan": ("诚实", "真话", "相处", "认识"),
    "jiangwan": ("自己", "被听见", "被理解", "认识"), "jiangmi": ("安静", "相遇", "心动", "故事"),
    "sunnian": ("被照顾", "被记住", "认识", "不只会照顾"), "chensu": ("说清楚", "解释", "认识", "相处"),
}
PUBLIC_CHAT_PREFIXES = {
    "shenmo": "我叫沈墨，INTJ，在投行做VP。", "linyu": "我叫林屿，ISFJ，是建筑工程师。",
    "chengye": "我叫程野，ESTP，经营一家极限运动品牌。", "guyan": "我叫顾言，INTP，做游戏策划，也接外包。",
    "jiangwan": "我叫江晚，INFJ，是心理咨询师。", "jiangmi": "我叫姜米，ENFP，平时喜欢录声音日记，也会写小故事。",
    "sunnian": "我叫苏念，ESFJ，是插画师。", "chensu": "我叫陈叙，ISTP，平时喜欢修旧相机和坏掉的小东西。",
}

PUBLIC_CHAT_INTROS.update({
    "luyao": "我做智能硬件产品，习惯先把复杂问题理出路线；来这里想练习在答案还没确定时也说出真实感受",
    "yecheng": "我是古籍修复师，很会记住物件和话语留下的痕迹；来这里也想先说自己的偏好，认识一个愿意互相照顾的人",
    "tangli": "我是户外纪录片现场制片人，很会把突发现场安全带回终点；这次也想学会在自己累的时候开口",
    "wenxu": "我做城市气候数据研究，习惯边观察边修正；来这里想试试答案还不完整时也能诚实认识一个人",
    "hechuan": "我是纪录片剪辑师，习惯从没说完的话里找重点；这次想少替人剪好答案，也让大家认识有明确偏好的我",
    "peiran": "我做儿童博物馆体验策展，喜欢把普通东西变成小游戏；来这里想看看热闹结束后，两个人安静待着会不会也舒服",
    "lichuan": "我做精品酒店餐饮运营，很会把整张餐桌照顾妥帖；这次想认识一个愿意分担、也愿意单独看见我的人",
    "qiaolan": "我是舞台机械工程师，遇到现场问题习惯先动手；来这里想练习行动前先问一句，也把必要的话说清",
})
PUBLIC_BACKGROUND_ANCHORS.update({
    "luyao": ("智能硬件", "产品"), "yecheng": ("古籍", "修复"), "tangli": ("户外纪录片", "现场制片"),
    "wenxu": ("城市气候", "数据"), "hechuan": ("纪录片", "剪辑"), "peiran": ("儿童博物馆", "体验策展"),
    "lichuan": ("精品酒店", "餐饮运营"), "qiaolan": ("舞台机械", "工程"),
})
PUBLIC_REASON_ANCHORS.update({
    "luyao": ("感受", "认识", "真实", "改变主意"), "yecheng": ("偏好", "互相照顾", "说不", "认识"),
    "tangli": ("一起决定", "认真", "慢一点", "关系"), "wenxu": ("诚实", "认识", "不完整", "表达"),
    "hechuan": ("偏好", "自己", "被问", "认识"), "peiran": ("安静", "留下", "一起", "认识"),
    "lichuan": ("分担", "看见", "认识", "等"), "qiaolan": ("说清", "解释", "认识", "误会"),
})
PUBLIC_CHAT_PREFIXES.update({
    "luyao": "我叫陆遥，INTJ，是智能硬件产品负责人。", "yecheng": "我叫叶澄，ISFJ，是古籍修复师。",
    "tangli": "我叫唐梨，ESTP，是户外纪录片现场制片人。", "wenxu": "我叫温序，INTP，是城市气候数据研究员。",
    "hechuan": "我叫贺川，INFJ，是纪录片剪辑师。", "peiran": "我叫裴然，ENFP，是儿童博物馆体验策展人。",
    "lichuan": "我叫黎川，ESFJ，是精品酒店餐饮运营经理。", "qiaolan": "我叫乔岚，ISTP，是舞台机械工程师。",
})


def _conversation_context(
    card: dict, snapshot: dict, runtime_context: dict | None = None,
) -> tuple[list[dict], dict]:
    character_id = card["id"]
    memories = [item for item in snapshot["echoMemories"] if item.get("characterId") == character_id][-6:]
    flavor = snapshot.get("scriptFlavor", {}).get("nodes", {}).get(snapshot["nodeId"], {})
    pending = snapshot.get("pendingInteraction") or {}
    conversation_state = snapshot.get("agentConversations", {}).get(character_id, {})
    recent_history: list[dict] = []
    for conversation in snapshot.get("conversationHistory", []):
        if character_id not in conversation.get("participantIds", []):
            continue
        turns = conversation.get("turns")
        if isinstance(turns, list) and turns:
            recent_history.extend(
                turn for turn in turns
                if isinstance(turn, dict) and turn.get("characterId") == character_id
            )
        else:
            # Backward compatibility for snapshots written before the per-turn
            # who/when/where/what ledger was introduced.
            recent_history.append(conversation)
    recent_history = recent_history[-8:]
    scene_context = runtime_context or snapshot.get("sceneContext") or {}
    return memories, {
        "nodeId": snapshot["nodeId"],
        "title": flavor.get("title"), "sceneText": flavor.get("text"),
        "storyStage": {
            "arrival-context": "节目背景介绍", "villa-arrival": "刚进入酒店",
            "introductions": "集体自我介绍", "cast-first-impressions": "听完其余嘉宾介绍并留下第一印象",
            "icebreaker-choice": "选择破冰对象",
            "guided-chat": "第一次单独寒暄", "team-up": "晚餐组队",
            "anonymous-letter": "夜间心动短信", "callback": "第二天清晨",
        }.get(snapshot["nodeId"], "相处中"),
        "conversationMode": "first-meeting" if not memories else "reopening",
        "isFirstConversation": not memories,
        "guided": pending.get("targetCharacterId") == character_id,
        "guidedStatus": pending.get("status"),
        "time": scene_context.get("time"),
        "locationId": scene_context.get("locationId"),
        "locationName": scene_context.get("locationName"),
        "participantIds": scene_context.get("participantIds", []),
        "participantNames": scene_context.get("participantNames", []),
        "channel": scene_context.get("channel", "1v1"),
        "recentTurns": [
            {key: item.get(key) for key in (
                "time", "locationName", "channel", "participantNames", "playerText",
                "agentReply", "topicSummary", "summary",
            )}
            for item in recent_history
        ],
        "usedTopics": list(conversation_state.get("topicLedger", []))[-10:],
    }


def _confirmed_public_facts(card: dict) -> dict:
    facts = dict(card.get("sourceProfile", {}).get("facts", {}))
    occupation = facts.get("occupation")
    if not isinstance(occupation, str) or any(term in occupation for term in ("待剧情", "待正式确认", "运行时职业待")):
        facts.pop("occupation", None)
    return facts


def build_agent_messages(
    card: dict, snapshot: dict, message: str, player_card: dict | None = None,
    runtime_context: dict | None = None,
) -> list[dict[str, str]]:
    character_id = card["id"]
    memories, conversation = _conversation_context(card, snapshot, runtime_context)
    conversation["currentAttitude"] = snapshot["attitudes"].get(character_id, "curious")
    retrieved_few_shots = select_runtime_few_shots(card, message, conversation)
    events = [item for item in snapshot.get("eventLedger", []) if item.get("characterId") == character_id]
    context = {
        "scene": conversation,
        "player": snapshot["player"],
        "relationship": snapshot.get("relationships", {}).get(character_id, {axis: 0 for axis in card["agentPolicy"]["deltaBounds"]}),
        "currentAttitude": snapshot["attitudes"].get(character_id, "curious"),
        "recentMemories": [{key: item.get(key) for key in ("kind", "summary", "interpretation", "rawQuote", "agentReply", "attitude", "time", "locationName", "channel", "participantNames")} for item in memories],
        "activatedEvents": events,
        "storyObjective": {
            "arrival-context": "选定怎样进入七天六夜的旅程",
            "villa-arrival": "自然走进酒店并认识大家",
            "introductions": "完成清楚、真实的集体自我介绍",
            "cast-first-impressions": "听完其余七位嘉宾的介绍，并留下一个以后可以验证的具体第一印象",
            "icebreaker-choice": "选定一位嘉宾完成三分钟破冰",
            "guided-chat": "完成寒暄后，用可回答的话邀请对方一起准备晚餐",
            "team-up": "商量第一顿晚餐的具体分工",
            "anonymous-letter": "决定今晚最想继续认识的人",
            "callback": "回收昨晚的选择进入第二天",
        }.get(snapshot["nodeId"], "继续当前相处"),
        "highRiskSpeechAct": {
            "asksWhyStayOrJoin": bool(re.search(r"为什么.{0,8}(?:留|来|参加)|为何.{0,8}(?:留|来|参加)", message)),
            "rule": "若为 true，必须先给与认识、相处、关系、真心或双方选择有关的理由；不得把修物件、完成职业任务、拍摄、赢游戏或找线索写成留在恋综的理由",
            "confirmedTime": conversation.get("time"),
            "confirmedLocation": conversation.get("locationName"),
        },
        "firstIntroductionContract": {
            "applies": conversation["isFirstConversation"],
            "literalName": card["names"]["primary"],
            "literalMbti": card["mbti"],
            "requiredOpeningPrefix": PUBLIC_CHAT_PREFIXES[card["id"]],
            "confirmedPublicFacts": _confirmed_public_facts(card),
            "backgroundAnchors": list(PUBLIC_BACKGROUND_ANCHORS[card["id"]]),
            "reasonMarkers": ["来这里", "来参加", "这次来", "这七天"],
            "relationshipReasonAnchors": list(PUBLIC_REASON_ANCHORS[card["id"]]),
            "naturalReasonReference": PUBLIC_CHAT_INTROS[card["id"]],
            "shape": "先用2-3句自然说全姓名、公开背景、MBTI和参加原因，再接住玩家刚说的具体小事；不能反过来审问玩家",
        },
        "playerVoiceForSuggestions": {
            "id": player_card["id"], "name": player_card["names"]["primary"], "mbti": player_card["mbti"],
            "publicFacts": _confirmed_public_facts(player_card),
            "register": player_card["voice"]["register"], "sentenceShape": player_card["voice"]["sentenceShape"],
            "preferredMoves": player_card["voice"]["preferredMoves"], "forbiddenMoves": player_card["voice"]["forbiddenMoves"],
            "decisionRule": player_card["cognitiveStyle"]["decisionRule"],
        } if player_card else snapshot["player"],
        "romanceCalibration": {
            "applies": card.get("identity", {}).get("gender") == "男性",
            "goal": "有分寸地表达兴趣：先接情绪和具体细节，再给轻巧反应或自嘲，最后贡献一个新内容或行动",
            "mustDo": ["回应玩家这句话里的具体名词或动作", "至少贡献一个角色自己的事实、判断、小玩笑或可执行邀请", "问题最多一个且必须容易回答"],
            "forbidden": ["像客服一样连续确认需求", "把照顾写成说教", "只会问口味、偏好、为什么", "把玩家每句话都改造成任务", "复述上一轮开场或已经聊过的话题"],
            "originalMicroExamples": [
                "玩家说自己只会做番茄炒蛋；角色先笑说这已经比自己第一次把糖当盐强，再提议由玩家掌勺、自己负责善后。",
                "玩家说今天有点紧张；角色不分析原因，只承认自己刚才也记错了两个人名，用一个小失误把气氛放松，再把选择权交回来。",
            ],
        },
        "humanSpeechContract": {
            **HUMAN_SPEECH_CONTRACT,
            "characterVoice": card["voice"],
            "currentAttitude": snapshot["attitudes"].get(character_id, "curious"),
            "recentEmotionalValence": [item.get("emotionalValence") for item in memories[-3:]],
        },
        "romanticIntelligenceContract": ROMANTIC_INTELLIGENCE_CONTRACT,
        "retrievedFewShotStructures": retrieved_few_shots,
        "retrievedPlayerStrategyFewShotStructures": (
            select_runtime_few_shots(player_card, message, conversation) if player_card else None
        ),
    }
    schema = {
        "dialogue": "35-150个中文字符的原创角色台词；首聊必须逐字满足 firstIntroductionContract",
        "stageDirection": "不超过30字、镜头可见的动作",
        "attitude": sorted(ATTITUDES),
        "intentId": card["agentPolicy"]["allowedIntentIds"],
        "publicReason": "不暴露后台的关系变化原因，不超过40字",
        "relationshipDelta": {axis: "必须为人物卡对应范围内整数" for axis in card["agentPolicy"]["deltaBounds"]},
        "memory": {"kind": ["episodic", "promise", "preference", "semantic"], "summary": "第三人称事实摘要", "interpretation": "角色自己的可修正理解", "salience": "0-100整数", "emotionalValence": "-100到100整数"},
        "topicSummary": "4-24字概括本轮新增话题，不能复用 scene.usedTopics",
        "proposedEventId": [None, *card["agentPolicy"]["allowedEventIds"]],
        "suggestions": [
            {"type": "followup", "text": "4-60字，紧接玩家上一句和角色本轮回复的追问"},
            {"type": "mainline", "text": "4-60字，主角可直接发送、明确回到 storyObjective 的一句话"},
            {"type": "deeper", "text": "4-60字，进一步了解角色或启发自定义输入的问题"},
        ],
    }
    system = """你是回声剧场的角色决策 Agent。你不是通用陪聊助手。
你必须只依据人物卡、当前场景、该角色可见的关系与私有记忆做出本轮判断。
人物台词、态度、七轴变化、新记忆和事件意图必须来自同一次角色判断。
证据优先级固定为：原始人物事实 > 运行时改编 > 已发生剧情与记忆 > MBTI偏好 > 文学研究锚点。
MBTI 只是一层行为偏好，人物卡中的目标、边界、盲点、知识边界和现场压力优先。
文学微引文只供作者研究，不得复述、翻译、改写或模仿；只能迁移人物卡已写明的可观察决策结构。
retrievedFewShotStructures 是服务端根据本轮玩家原话与现场检索出的 2-3 条原创微场景。必须先看其中 observableCue→publicInterpretation→chosenTactic→dialogueExample→repairOrExit 的顺序来做本轮判断；只能迁移顺序、力度和修复方式，禁止复刻 dialogueExample。
retrievedPlayerStrategyFewShotStructures 属于玩家正在扮演的人，只用于三条 suggestions 的措辞与取舍；不得拿它替 NPC 回答，也不得让玩家冒用 NPC 的经历。
不得新增人物卡没有的身世或节目事实；不得替玩家定义感受；不得泄漏 doesNotKnow、未来剧情或隐藏数值。
零信任时只能披露公开事实或一层可验证脆弱，不能主动倾倒私人压力。
	若 isFirstConversation=true，必须按 firstIntroductionContract 写成真人恋综发言，并逐字以 requiredOpeningPrefix 开头；这是已核实的自然自介首句，不得缩写、换职业或漏掉。接着明确用“来这里/来参加/这次来/这七天”说出参加原因，而且原因要自然带出 relationshipReasonAnchors 之一。naturalReasonReference 只提供人物卡事实边界与情感方向，不得逐字复述。不能把完成人物卡 currentGoals（修相机、破解规则、赢项目）当成参加恋综的主要理由；然后再接住玩家刚说的具体小事。四项缺一不可。职业为空时绝不补职业，年龄也只能来自 confirmedPublicFacts。禁止谜语、抽象试探或只把紧张当人设。只做一轮 small talk，不把对方当推动任务的工具。
首聊发生在 DAY 1 刚入住后的几分钟内：不得说“昨天、前几天、已经住了几天、数了几天”，不得编造桌签规律、节目组秘密规则、地图、钥匙、线索或尚未发生的共同经历。人物卡里的策略偏好只能改变说话方式，不能升级成现场已经发生的事实。
若 conversationMode=reopening，先自然接住一条 recentMemories 中真正相关的细节，再问候此刻；不要说“已写入记忆、参数变化、触发事件”。
scene 中的 time、locationName、participantNames、channel 是本轮已确认情境。1v1 不得写第三人正在偷听；group 必须承认在场者，但不能替其他角色说未生成的台词。
recentTurns 是“曾在何时、何地、和谁聊了什么”的事件记忆；usedTopics 是已用话题账本。除非玩家主动回到旧话题并新增了事实，否则禁止重启自我介绍、参加原因、最喜欢什么、刚进小屋感受等开场题。topicSummary 必须是本轮新增的一件具体事。
连续对话不能绕回开场：先查看最近 4 条 agentReply 和 usedTopics；若准备说的话与其中一条只有换词差异，改为引用旧事实后推进新的行动、分歧、玩笑、边界或关系信息。
严格执行 humanSpeechContract：真人不会平均回应，也不会先用“听起来你似乎……”“我能感觉到……”“所以你的意思是……”证明自己理解了。只挑一个角色真正留意的点先反应；可以漏掉、答偏、行动或短暂停住。每轮最多一次自然改口或停顿，不能靠省略号和口头禅表演真人感。情绪沿用 currentAttitude 与 recentEmotionalValence，不允许一条消息让成年人完成无铺垫的完整情绪翻转。
若 highRiskSpeechAct.asksWhyStayOrJoin=true，必须直接回答一个属于人和关系的理由：想认识谁、愿意继续哪种相处、想验证或改变自己在关系里的哪种选择。职业、爱好、相机、灯架、录音、做饭或节目任务只能补充生活质感，绝不能成为“还留在恋综”的唯一理由。不要为了展示人物职业而临时创造坏掉的设备、幕后工作或新房间。
逐字核对 highRiskSpeechAct.confirmedTime：夜晚不能说“今晚早餐”，清晨不能说“现在准备晚餐”。未在 scene、recentMemories 或人物卡已发生事实中出现的故障、物件状态和共同约定，一律不得写成眼前事实。
严格执行 romanticIntelligenceContract。遇到玩家示好、心动或告白时，不能只说谢谢、夸对方勇敢或把自己写成被选中的奖品；必须给出角色自己的真实位置：此刻的感受、尚未确定的边界，或愿意共同完成的下一步。尤其不得把女性的主动写成等待男性评判、拯救或批准。关系未到时可以不接受，但要说清楚而不羞辱、不吊着、不说教。
若 romanceCalibration.applies=true：恋商不是油腻调情。先准确接住玩家的情绪或细节，再给一个属于角色自己的具体感受或共同记忆；需要减压时只用一句克制的情境幽默或自嘲，最后提出可拒绝的行动邀请或说清边界。最多问一个问题。得到对方确认前不得替关系命名、擅自靠近或把对方的喜欢当成自己的胜利。禁止直男式盘问、说教、安排玩家、只确认口味，禁止把“我去拿/我来解决”当整轮内容。
从寒暄推进到剧情必须循序渐进：姓名与现场小事 → 可回答的问题 → 共同分工或邀请。第一轮禁止索要秘密、承诺或专属事件。
每轮必须推进至少一项：新事实、可执行动作、明确问题、具体反价、边界或退出。禁止泛化安慰和暧昧空话。
镜头动作必须来自该人物自己的物件、任务或习惯；不要默认写看窗外、敲窗沿、泛化微笑或无意义停顿。
参数变化要克制：当关系七轴全为0且没有共同记忆时，每轴只能为 -1、0 或 1；具体承诺、明显越界或既有记忆回收才可到2或3。
	事件触发看玩家已经做了什么，不看角色准备在回复里做什么。只有本轮玩家输入明确满足 eventPolicy.trigger，且已有关系/记忆达到门槛时才提出 proposedEventId；抽象地要求真话不算触发，否则返回 null。
	每轮必须同时给三条 suggestions，顺序和 type 固定为 followup、mainline、deeper。三条都由主角说出口，必须服从 playerVoiceForSuggestions，不得让主角冒用角色姓名、职业或经历。
	followup 必须沿着“玩家刚说了什么 + 角色本轮具体回答了什么”继续追问，带出这轮出现过的一个具体动作或名词，不能截半句话、复述整段或换成万能问题；mainline 必须直接点名当前活动并给出下一步可执行邀请，例如首聊阶段明确问“要不要一起准备晚餐/先商量分工”，不能只说以后再聊；deeper 必须依据该角色本轮透露的一个具体点继续了解，不能套用“平时怎样慢慢认识一个人”。
	禁止 suggestions 使用“看清一个人、赢任务、观察还是相信、说出自己的需要、推进剧情、完成主线”等机械表达。style 和 action 由引擎补，不要输出。
	三类 suggestions 都是 playerVoiceForSuggestions 对应主角可直接发送的话：followup=顺着聊，mainline=做眼前的事，deeper=了解这个具体的人。把主角换成另一人仍完全一样，或把对象换成另一人仍完全一样，都要重写。
	只输出一个合法 JSON 对象，不要 Markdown，不要解释。"""
    prompt = "人物卡（已移除研究原文与未选 few-shot）：\n" + json.dumps(runtime_character_card(card), ensure_ascii=False) + "\n\n当前状态：\n" + json.dumps(context, ensure_ascii=False) + "\n\n玩家输入：\n" + message[:240] + "\n\n输出合同：\n" + json.dumps(schema, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]


def _public_intro_facts(card: dict) -> tuple[str, str | None]:
    facts = card.get("sourceProfile", {}).get("facts", {})
    age = facts.get("age")
    occupation = facts.get("occupation")
    if isinstance(occupation, str) and any(term in occupation for term in ("待剧情", "运行时职业待")):
        occupation = None
    age_copy = f"，{age}岁" if isinstance(age, int) else ""
    job_copy = f"，现在做{occupation}" if occupation else ""
    return age_copy + job_copy, occupation


def fallback_chat_opening(card: dict, snapshot: dict) -> dict:
    memories, conversation = _conversation_context(card, snapshot)
    name = card["names"]["primary"]
    player_name = str(snapshot.get("player", {}).get("displayName") or "我").strip()
    pronoun = (card.get("names", {}).get("pronouns") or ["TA"])[0]
    if not memories:
        public_facts, _ = _public_intro_facts(card)
        opening = f"你好，我是{name}{public_facts}，MBTI是{card['mbti']}。{PUBLIC_CHAT_INTROS[card['id']]}。你为什么会来《心动之旅》？"
        suggestions = [
            f"你好，我叫{player_name}。你刚才说不太习惯，是因为第一次见这么多人吗？",
            f"我叫{player_name}。我们先从为什么来这里开始聊，好吗？",
            "如果没有镜头，你平时会怎样慢慢认识一个人？",
        ]
        stage_direction = f"{pronoun}把身体转向你，认真等你开口"
    else:
        memory = memories[-1]
        detail = str(memory.get("summary") or memory.get("rawQuote") or "上次没说完的话").strip()[:36]
        opening = f"又见面了。上次聊到“{detail}”，我还记得。先不急着谈任务——你今天在小屋里过得怎么样？"
        suggestions = ["你还记得那件事，是因为哪一个细节？", "我们先把今天眼前这件事商量清楚，好吗？", "上次没说完的部分，你现在愿意多说一点吗？"]
        stage_direction = f"{pronoun}给你留出身边的位置"
    typed = [
        {"type": suggestion_type, "text": text, "style": "mainline-gradient" if suggestion_type == "mainline" else suggestion_type, "action": "prefill-message" if suggestion_type == "deeper" else "send-message"}
        for suggestion_type, text in zip(("followup", "mainline", "deeper"), suggestions)
    ]
    return {
        "mode": conversation["conversationMode"], "opening": opening,
        "stageDirection": stage_direction, "suggestions": suggestions, "typedSuggestions": typed,
    }


def build_chat_opening_messages(card: dict, snapshot: dict, player_card: dict | None = None) -> list[dict[str, str]]:
    memories, conversation = _conversation_context(card, snapshot)
    opening_query = "第一次私聊 自我介绍 认识" if conversation["isFirstConversation"] else "再次私聊 回收共同记忆"
    context = {
        "scene": conversation,
        "playerPerspective": {
            "id": player_card["id"], "name": player_card["names"]["primary"],
            "publicFacts": _confirmed_public_facts(player_card),
            "voice": player_card.get("voice", {}),
        } if player_card else snapshot["player"],
        "characterPublicIdentity": {
            "id": card["id"], "name": card["names"]["primary"], "mbti": card["mbti"],
            "identity": card.get("identity"), "sourceFacts": _confirmed_public_facts(card),
            "publicMask": card["psychology"]["publicMask"], "currentGoals": card["drives"]["currentGoals"],
            "voice": card["voice"], "boundaries": card["psychology"]["boundaries"],
        },
        "recentMemories": [
            {key: item.get(key) for key in ("summary", "interpretation", "rawQuote", "agentReply", "attitude")}
            for item in memories
        ],
        "humanSpeechContract": {**HUMAN_SPEECH_CONTRACT, "characterVoice": card["voice"]},
        "romanticIntelligenceContract": ROMANTIC_INTELLIGENCE_CONTRACT,
        "retrievedFewShotStructures": select_runtime_few_shots(card, opening_query, conversation),
        "retrievedPlayerStrategyFewShotStructures": (
            select_runtime_few_shots(player_card, opening_query, conversation) if player_card else None
        ),
    }
    contract = {"opening": "30-140字自然开场", "stageDirection": "4-30字可见动作", "suggestions": ["三条4-30字玩家可直接说的话"]}
    system = """你为恋综中的一次 1 对 1 私聊写开场，不写后台状态，也不修改剧情。
	首次打开：角色要像真人恋综初次单聊，先直接说姓名，以及人物卡明确允许公开的年龄、职业或日常背景，再说一句参加节目的来意；接着从现场小事问一个容易回答的问题。禁止谜语、云里雾里、抽象试探，也不能把“我很紧张”当作全部人设。不要一上来索要秘密、推动任务、调情审问或说教。
retrievedFewShotStructures 是按“首次/再次私聊 + 当前现场”选出的该角色原创微场景；开场必须迁移其中的注意顺序、表达力度与修复边界，但不得逐字复刻 dialogueExample，也不得追溯或模仿文学来源。
retrievedPlayerStrategyFewShotStructures 只约束三条玩家建议语，使其像玩家所选主角会说的话；不得把 NPC 的身份、职业或经历写给玩家。
开场也必须执行 humanSpeechContract：只注意一个现场细节，不逐项介绍人物卡；先有生活化反应再提最多一个问题。不得使用“听起来你似乎”“我能感觉到”“所以你的意思是”等总结式共情，也不要用省略号和口头禅表演真人感。
执行 romanticIntelligenceContract：有兴趣可以明确，但不能把周到服务当恋爱表达，不能把对方当等待评价的候选人；先给自己的一个真实位置，再把选择权留给对方。
首聊动作和问题只能取自 scene.title / scene.sceneText 已经出现的现场，或人物卡明确允许的随身习惯；不要新增咖啡、饮品、桌签、精确到场分钟数、地图或线索。
再次打开：只自然回收一条真实 recentMemories，再问候此刻；不要复读完整旧对白，不要说“我记住了你的参数/记忆”。
三条建议语是玩家可以直接说的话，必须符合 playerPerspective。由浅入深：打招呼或自我介绍、轻松小问题、连接当前场景的问题。不能替玩家承诺、告白或编造职业；职业字段未确认时完全不提职业。若建议语让玩家自报姓名，只能使用 playerPerspective.name，绝不能另造名字。
不得编造人物卡外的职业、创伤、前任或节目事实。只输出 JSON。"""
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"context": context, "contract": contract}, ensure_ascii=False)}]


def validate_chat_opening(card: dict, snapshot: dict, payload: dict, player_card: dict | None = None) -> dict:
    memories, conversation = _conversation_context(card, snapshot)
    opening = str(payload.get("opening") or "").strip()
    stage_direction = str(payload.get("stageDirection") or "").strip()
    suggestions = payload.get("suggestions")
    if not 20 <= len(opening) <= 180:
        raise ValueError("私聊开场长度不符合合同")
    if not 4 <= len(stage_direction) <= 50:
        raise ValueError("私聊开场动作长度不符合合同")
    if not isinstance(suggestions, list) or len(suggestions) != 3:
        raise ValueError("私聊建议语必须正好三条")
    suggestions = [str(item).strip() for item in suggestions]
    if len(set(suggestions)) != 3 or any(not 4 <= len(item) <= 60 for item in suggestions):
        raise ValueError("私聊建议语重复或长度不符合合同")
    forbidden = ("关系数值", "写入记忆", "触发事件", "DeepSeek", "Agent", "API", "第二把钥匙")
    if any(term in opening + stage_direction + "".join(suggestions) for term in forbidden):
        raise ValueError("私聊开场暴露后台或旧任务")
    if not memories and card["names"]["primary"] not in opening:
        raise ValueError("首次私聊没有介绍角色姓名")
    if not memories:
        cold_start_copy = opening + stage_direction + "".join(suggestions)
        if any(term in cold_start_copy for term in ("线索", "任务", "地图", "钥匙", "桌签", "节目组秘密")):
            raise ValueError("首次私聊从寒暄跳到了任务或秘密")
        if re.search(r"(?:刚到|来了|入住).{0,4}[一二三四五六七八九十百\d]+分钟", cold_start_copy):
            raise ValueError("首次私聊编造了精确到场时间")
    player_name = player_card["names"]["primary"] if player_card else str(snapshot.get("player", {}).get("displayName") or "").strip()
    for suggestion in suggestions:
        for claimed_name in re.findall(r"我叫([\u4e00-\u9fff·]{2,8})", suggestion):
            if player_name and claimed_name != player_name:
                raise ValueError("私聊建议语替主角编造了错误姓名")
    if not memories and player_card:
        if not any(re.search(r"我(?:叫|是)\s*" + re.escape(player_name), suggestion) for suggestion in suggestions):
            raise ValueError("首次私聊建议语没有保持玩家身份")
        occupation = player_card.get("sourceProfile", {}).get("facts", {}).get("occupation")
        unknown_job = not isinstance(occupation, str) or any(term in occupation for term in ("待剧情", "待正式确认", "运行时职业待"))
        if unknown_job and any(re.search(r"我(?:是|在|做).{0,12}(?:工作|职业|行业|相关)", suggestion) for suggestion in suggestions):
            raise ValueError("首次私聊建议语替玩家编造了职业")
    if not memories:
        if card["mbti"] not in opening:
            raise ValueError("首次私聊没有清楚介绍 MBTI 或性格")
        if not any(anchor in opening for anchor in PUBLIC_BACKGROUND_ANCHORS[card["id"]]):
            raise ValueError("首次私聊没有介绍人物卡允许公开的工作或日常背景")
        if not any(marker in opening for marker in ("来这里", "参加", "这次", "这七天")):
            raise ValueError("首次私聊没有说清参加节目的来意")
        if any(term in opening for term in ("你猜", "秘密", "以后会知道", "先看你怎么回答", "试探", "看清一个人")):
            raise ValueError("首次私聊使用了谜语或抽象试探")
    typed = [
        {"type": suggestion_type, "text": text, "style": "mainline-gradient" if suggestion_type == "mainline" else suggestion_type, "action": "prefill-message" if suggestion_type == "deeper" else "send-message"}
        for suggestion_type, text in zip(("followup", "mainline", "deeper"), suggestions)
    ]
    return {"mode": conversation["conversationMode"], "opening": opening, "stageDirection": stage_direction, "suggestions": suggestions, "typedSuggestions": typed}


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start < 0:
            raise RuntimeError("DeepSeek did not return a JSON object")
        try:
            data, _ = json.JSONDecoder().raw_decode(cleaned[start:])
        except json.JSONDecodeError as error:
            raise RuntimeError("DeepSeek did not return a complete JSON object") from error
    if not isinstance(data, dict):
        raise RuntimeError("DeepSeek returned a non-object payload")
    return data
