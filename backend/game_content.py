"""EchoCore-compatible story state and validated DeepSeek Agent commits."""
from __future__ import annotations

import json
import re
from hashlib import sha256
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
RELATIONSHIP_AXES = ("trust", "affection", "respect", "fear", "debt", "attraction", "resentment")
ATTITUDES = {"warm", "curious", "guarded", "challenging", "vulnerable", "softened", "uncertain", "honest", "moved", "careful", "steady", "boundary"}
CONTENT_VERSION = "3.8.0-humanlike-fewshots"
CHAT_CONTEXT_VERSION = 1
CHAT_LOCATIONS = {
    "hotel-entrance": {"name": "酒店玄关", "supportsGroup": True},
    "living-room": {"name": "客厅", "supportsGroup": True},
    "terrace": {"name": "海景露台", "supportsGroup": True},
    "luggage-area": {"name": "行李区", "supportsGroup": True},
    "kitchen": {"name": "开放厨房", "supportsGroup": True},
    "dining-room": {"name": "餐厅", "supportsGroup": True},
    "bedroom": {"name": "卧室", "supportsGroup": False},
}
NODE_SCENE_CONTEXT = {
    "arrival-context": ("DAY 1 · 18:18", "hotel-entrance"),
    "villa-arrival": ("DAY 1 · 18:20", "hotel-entrance"),
    "introductions": ("DAY 1 · 18:35", "living-room"),
    "cast-first-impressions": ("DAY 1 · 18:48", "living-room"),
    "icebreaker-choice": ("DAY 1 · 18:55", "living-room"),
    "guided-chat": ("DAY 1 · 19:05", "living-room"),
    "team-up": ("DAY 1 · 19:25", "kitchen"),
    "anonymous-letter": ("DAY 1 · 22:30", "bedroom"),
    "callback": ("DAY 2 · 08:10", "dining-room"),
}
INTRODUCTION_MODES = {
    "intro-clear": "camera-full",
    "intro-question": "living-room-keepsake",
    "intro-honest": "contrast-full",
}
SUGGESTION_PRESENTATION = {
    "followup": {"style": "followup", "action": "send-message"},
    "mainline": {"style": "mainline-gradient", "action": "send-message"},
    "deeper": {"style": "deeper", "action": "prefill-message"},
}
MECHANICAL_COPY_TERMS = (
    "看清一个人", "赢任务", "观察还是相信", "先决定相信", "先决定观察", "说出自己的需要",
    "真正看见一个人", "行动目标", "关系目标", "共同信任目标", "建立信任", "确立关系",
    "推进剧情", "完成主线", "最具体的是哪一部分", "如果先不考虑节目镜头",
)

INTRODUCTION_FALLBACKS: dict[str, dict[str, tuple[str, str]]] = {
    "shenmo": {
        "intro-clear": ("大家好，我叫沈墨，29岁，在投行做VP，MBTI是INTJ。平时习惯先把问题想清楚；这次来参加，是想练习在答案还没出来时，也把真实感受说出来。", "镜头前把姓名、工作、性格和来意一次说清"),
        "intro-question": ("我是沈墨，投行VP，INTJ。我来这里想慢一点认识人，不急着给答案。你们第一天最怕别人误会自己哪一点？", "简短介绍后，问一个每个人都能回答的问题"),
        "intro-honest": ("我叫沈墨，29岁，在投行做VP，MBTI是INTJ。看起来可能有点难接近；其实我来参加，是想遇到一个不催我给答案、但愿意等我把话说完的人。", "说清公开信息，也承认冷静外表后的真实期待"),
    },
    "linyu": {
        "intro-clear": ("大家好，我叫林屿，27岁，是建筑工程师，MBTI是ISFJ。我来这里，是想少一点照顾所有人，也认识一个会问问我感受的人。", "姓名、工作和参加原因都说得清楚"),
        "intro-question": ("我是林屿，建筑工程师，ISFJ。我来参加，是想少替别人拿主意，也先问问自己想做什么。你们刚进门时，最希望别人帮你哪件小事？", "用一个生活化的问题让客厅自然接话"),
        "intro-honest": ("我叫林屿，27岁，做建筑，MBTI是ISFJ。大家常觉得我很会照顾人；但这次来这里，我也想知道，不主动递水时，会不会有人先问我渴不渴。", "不把体贴当完美人设，坦白自己也想被照顾"),
    },
    "chengye": {
        "intro-clear": ("大家好，我叫程野，26岁，经营一家极限运动品牌，MBTI是ESTP。我来参加，是想认真认识一个人，也认真完成一次说出口的约定。", "直接交代姓名、工作、性格和这次来意"),
        "intro-question": ("我是程野，做极限运动品牌，ESTP。我来这里想把这七天过得痛快，也把答应的事做完。你们最想和大家一起试哪件事？", "轻快开场，再抛出一个能聊到行动的问题"),
        "intro-honest": ("我叫程野，26岁，做极限运动品牌，MBTI是ESTP。看着像什么都敢冲；其实这次来参加，我更想试试遇到状况时不绕开，认真陪一个人把话说完。", "保留爽快，也说出不逃开的反差来意"),
    },
    "guyan": {
        "intro-clear": ("大家好，我叫顾言，25岁，做游戏策划，也接外包，MBTI是INTP。我来参加，是想试试不等到答案完美，也能和人诚实相处。", "信息说全，不把自我介绍讲成一道题"),
        "intro-question": ("我是顾言，做游戏策划和外包，INTP。我来这里想少分析一会儿，先认识真实的人。你们更怕第一天冷场，还是被问得太快？", "用一个好回答的二选一，让大家自然接话"),
        "intro-honest": ("我叫顾言，25岁，游戏策划，MBTI是INTP。我确实不太会寒暄；但我来参加，不是为了研究别人，是想练习答案不够漂亮时也把真话说出来。", "承认笨拙，但不把人当成待验证的问题"),
    },
    "jiangwan": {
        "intro-clear": ("大家好，我叫江晚，26岁，是心理咨询师，MBTI是INFJ。工作里常听别人说；这次来参加，我想少分析一点，也让大家认识工作之外的我。", "把姓名、职业、性格和参加原因温和地说清"),
        "intro-question": ("我是江晚，心理咨询师，INFJ。我来这里想多说一点自己的事。你们刚进客厅时，最想先找谁聊一句什么？", "短介绍后把选择还给大家，问题容易回答"),
        "intro-honest": ("我叫江晚，26岁，做心理咨询，MBTI是INFJ。大家可能先觉得我很会倾听；其实这次来这里，我也希望有人先问问我想要什么。", "不分析别人，先坦白自己也希望被询问"),
    },
    "jiangmi": {
        "intro-clear": ("大家好，我叫姜米，ENFP。平时喜欢录声音日记，也会把偶遇写成小故事。我来参加，是想知道两个人不说漂亮话，只一起吹吹海风，也会不会心动。", "轻快说清姓名、日常背景、性格和来意"),
        "intro-question": ("嗨，我是姜米，ENFP，爱录声音日记，也爱写小故事。我来这里想遇见一些值得记住的声音。你们刚进门先记住的是海浪、行李轮，还是谁的一声你好？", "用眼前的声音开场，让每个人都有话可接"),
        "intro-honest": ("我叫姜米，ENFP，平时会录声音日记、写小故事。我看起来很能热场；其实来参加，是想试试安静下来时，也有人愿意继续坐在我旁边。", "承认热闹外表后的期待，但不故作神秘"),
    },
    "sunnian": {
        "intro-clear": ("大家好，我叫苏念，25岁，是插画师，MBTI是ESFJ。我来参加，是想认真过好这七天，也让大家认识不只会照顾人的我。", "明亮、完整地交代自己和这次来意"),
        "intro-question": ("我是苏念，插画师，ESFJ。我来这里想少忙着照顾所有人，也试试被别人记住。你们第一天最想吃到哪道家常菜？", "从晚餐前最容易接住的小问题开始聊天"),
        "intro-honest": ("我叫苏念，25岁，画插画，MBTI是ESFJ。看起来我很会张罗；但这次来参加，我不想只做收尾的人，也想体验一次被人认真照顾。", "承认自己也有需要，不再只维持气氛"),
    },
    "chensu": {
        "intro-clear": ("大家好，我叫陈叙，27岁，平时喜欢修旧相机和坏掉的小东西，MBTI是ISTP。我来参加，是想练习把该说的话也说清楚。", "不虚构职业，只说确认过的兴趣与来意"),
        "intro-question": ("我是陈叙，ISTP，平时喜欢修旧相机。我来这里，想和人一起做点具体的事。你们这七天最想一起完成什么？", "话不多，但给大家一个具体好答的问题"),
        "intro-honest": ("我叫陈叙，27岁，MBTI是ISTP，平时会修旧相机。看着话少，不代表不想认识人；这次来参加，我想试试先把原因说出来，再低头做事。", "保留行动派的简短，也把沉默解释清楚"),
    },
}
INTRO_BACKGROUND_ANCHORS = {
    "shenmo": ("投行",), "linyu": ("建筑",), "chengye": ("极限运动", "品牌"),
    "guyan": ("游戏", "外包"), "jiangwan": ("心理咨询",),
    "jiangmi": ("声音", "录音", "故事"), "sunnian": ("插画",), "chensu": ("相机", "修"),
}
INTRO_REASON_ANCHORS = {
    "shenmo": ("感受", "慢一点", "认识", "真实"),
    "linyu": ("照顾", "感受", "被对待", "认识"),
    "chengye": ("认真", "认识", "约定", "陪一个人"),
    "guyan": ("诚实", "真话", "相处", "认识"),
    "jiangwan": ("自己", "被听见", "被理解", "认识"),
    "jiangmi": ("安静", "相遇", "心动", "故事"),
    "sunnian": ("被照顾", "被记住", "认识", "不只会照顾"),
    "chensu": ("说清楚", "解释", "认识", "相处"),
}

INTRODUCTION_FALLBACKS.update({
    "luyao": {
        "intro-clear": ("大家好，我叫陆遥，28岁，是智能硬件产品负责人，MBTI是INTJ。我习惯把复杂的事情理出路线；来这里，是想练习在答案还没确定时，也把自己的感受告诉另一个人。", "把姓名、工作、性格和来意清楚说完"),
        "intro-question": ("我是陆遥，做智能硬件产品，INTJ。这次来，我想少替所有事预设结局，多认识真实的人。你们更喜欢提前计划，还是到现场再决定？", "简短介绍后留一个人人能答的问题"),
        "intro-honest": ("我叫陆遥，28岁，做智能硬件产品，MBTI是INTJ。看起来我很少犹豫；其实来这里，是想遇到一个能听见我改变主意、也不急着评价的人。", "说清果断外表下真实的关系期待"),
    },
    "yecheng": {
        "intro-clear": ("大家好，我叫叶澄，27岁，是古籍修复师，MBTI是ISFJ。我很会记住物件和话语留下的痕迹；来这里，是想学着先说自己的偏好，也认识一个愿意互相照顾的人。", "让大家先认识她体贴之外的明确愿望"),
        "intro-question": ("我是叶澄，古籍修复师，ISFJ。这次来，我想少一点替别人猜，多一点直接问。你们带来的哪件东西，最像现在的自己？", "用具体物件自然开启一轮接话"),
        "intro-honest": ("我叫叶澄，27岁，做古籍修复，MBTI是ISFJ。大家可能觉得我很有耐心；但我来这里，也想试试说不之后，仍然有人愿意好好认识我。", "承认温柔里也有清楚边界"),
    },
    "tangli": {
        "intro-clear": ("大家好，我叫唐梨，28岁，是户外纪录片现场制片人，MBTI是ESTP。我很会在突发现场把人和事情安全带回终点；来这里，也想学会在自己累的时候开口。", "爽快交代职业、性格和关系来意"),
        "intro-question": ("我是唐梨，做户外纪录片现场制片，ESTP。这次来，我想和大家把七天过得痛快，也把安全和边界说清楚。你们最想在岛上尝试什么？", "从共同体验切入但保留退出权"),
        "intro-honest": ("我叫唐梨，28岁，做户外纪录片现场制片，MBTI是ESTP。看着像什么都扛得住；其实来这里，我想遇到一个能在我说‘没事’之前看见我已经累了的人。", "把能扛现场之外会疲惫的一面说出来"),
    },
    "wenxu": {
        "intro-clear": ("大家好，我叫温序，26岁，是城市气候数据研究员，MBTI是INTP。我会为一阵反常的海风追很多组数据；来这里，是想试试答案只有七成时，也能先诚实认识一个人。", "信息具体，不把介绍讲成谜题"),
        "intro-question": ("我是温序，做城市气候数据研究，INTP。这次来，我想少在心里排练，多当场说出来。你们第一天更怕冷场，还是怕一句话说得不够漂亮？", "用好回答的二选一化开安静"),
        "intro-honest": ("我叫温序，26岁，做城市气候数据研究，MBTI是INTP。我说话可能会边说边改；来这里，是想认识一个允许我不完美表达、也愿意直接纠正我的人。", "承认笨拙而不故作高深"),
    },
    "hechuan": {
        "intro-clear": ("大家好，我叫贺川，30岁，是纪录片剪辑师，MBTI是INFJ。我常从别人没说完的话里找重点；来这里，是想少替别人剪好答案，也让大家认识有明确偏好的我。", "把倾听能力和自己的来意都说清"),
        "intro-question": ("我是贺川，纪录片剪辑师，INFJ。这次来，我想多说一点自己的答案。你们带来的一件东西里，哪件最能介绍现在的你？", "从具体物件邀请大家接话"),
        "intro-honest": ("我叫贺川，30岁，做纪录片剪辑，MBTI是INFJ。大家可能先觉得我很会理解人；其实来这里，我也希望有人不只被我听见，还会反过来问我想要什么。", "不做全场倾听工具人，先交出自己"),
    },
    "peiran": {
        "intro-clear": ("大家好，我叫裴然，27岁，是儿童博物馆体验策展人，MBTI是ENFP。我喜欢把普通东西变成不用分输赢的小游戏；来这里，是想看看热闹结束后，两个人安静坐着会不会也舒服。", "轻快说清职业、性格和真实期待"),
        "intro-question": ("嗨，我是裴然，做儿童博物馆体验策展，ENFP。这次来，我想认识一些愿意一起创造小事的人。你们小时候最喜欢把什么东西变成游戏？", "用轻松具体的问题让客厅自然热起来"),
        "intro-honest": ("我叫裴然，27岁，做儿童博物馆体验策展，MBTI是ENFP。我看起来很会热场；其实来这里，是想知道我不表演有趣的时候，会不会也有人愿意留下来。", "说出热闹外表后的安静需要"),
    },
    "lichuan": {
        "intro-clear": ("大家好，我叫黎川，29岁，是精品酒店餐饮运营经理，MBTI是ESFJ。我很会把整张餐桌照顾妥帖；来这里，是想认真认识一个也愿意分担、愿意单独看见我的人。", "明亮介绍，也交代互惠期待"),
        "intro-question": ("我是黎川，做精品酒店餐饮运营，ESFJ。这次来，我想少一点一个人收尾，多一点大家一起完成。你们最愿意负责今晚哪件小事？", "从自然分工认识每个人"),
        "intro-honest": ("我叫黎川，29岁，做精品酒店餐饮运营，MBTI是ESFJ。看起来我总能照亮全场；其实来这里，我想体验一次散场以后还有人单独等我的感觉。", "把会照顾全场和想被看见的反差说清"),
    },
    "qiaolan": {
        "intro-clear": ("大家好，我叫乔岚，28岁，是舞台机械工程师，MBTI是ISTP。我习惯在演出开始前把现场稳住；来这里，是想练习在行动之前先问一句，也把必要的话说清楚。", "职业、行动方式和来意都具体"),
        "intro-question": ("我是乔岚，做舞台机械工程，ISTP。这次来，我想和人一起做点具体的事，也不再让别人猜。你们这七天最想一起完成什么？", "话不多，但问题具体好回答"),
        "intro-honest": ("我叫乔岚，28岁，做舞台机械工程，MBTI是ISTP。看着像只会做不爱说；其实来这里，我想试试先解释一句，能不能让一段靠近少一点误会。", "保留利落，也承认表达是她的练习"),
    },
})
INTRO_BACKGROUND_ANCHORS.update({
    "luyao": ("智能硬件", "产品"), "yecheng": ("古籍", "修复"), "tangli": ("户外纪录片", "现场制片"),
    "wenxu": ("城市气候", "数据"), "hechuan": ("纪录片", "剪辑"), "peiran": ("儿童博物馆", "体验策展"),
    "lichuan": ("精品酒店", "餐饮运营"), "qiaolan": ("舞台机械", "工程"),
})
INTRO_REASON_ANCHORS.update({
    "luyao": ("感受", "认识", "改变主意", "真实"), "yecheng": ("偏好", "互相照顾", "说不", "认识"),
    "tangli": ("一起决定", "认真", "慢一点", "关系"), "wenxu": ("诚实", "认识", "不完美", "表达"),
    "hechuan": ("自己", "偏好", "被问", "认识"), "peiran": ("安静", "留下", "认识", "一起创造"),
    "lichuan": ("分担", "看见", "认识", "等我"), "qiaolan": ("说清楚", "解释", "认识", "误会"),
})

CAST_FIRST_IMPRESSION_FALLBACKS: dict[str, tuple[str, str]] = {
    "shenmo": (
        "我先记住沈墨。他介绍得很简洁，听别人说话时也没有抢着接话。",
        "晚餐分工时，我想看看他的克制会不会变成可靠的行动。",
    ),
    "linyu": (
        "我对林屿有点好奇。他把照顾别人说得自然，也承认自己不想总做收尾的人。",
        "之后一起做事时，我想看看有没有人会先顾到他的感受。",
    ),
    "chengye": (
        "我记住了程野。他接话很快，说到认真认识一个人时反而慢了下来。",
        "如果晚餐需要临时搭档，我想知道他会不会把玩笑后的话做到。",
    ),
    "guyan": (
        "我想再认识顾言。他承认自己不擅长寒暄，却没有拿分析代替真话。",
        "三分钟单聊时，我想听听他不准备标准答案会怎么说。",
    ),
    "jiangwan": (
        "我先记住江晚。她没有替任何人下结论，也清楚说了自己想被认识。",
        "今晚再聊时，我想把问题留给她，而不是只让她听别人说。",
    ),
    "jiangmi": (
        "我对姜米有点好奇。她把客厅带热了，也坦白自己安静下来时会更敏感。",
        "之后场面安静时，我想看看她会留下，还是先把气氛重新点亮。",
    ),
    "sunnian": (
        "我记住了苏念。她很会接住大家，也直接说不想只做照顾人的那一个。",
        "晚餐准备时，我想看看谁会主动把一件事从她手里接过去。",
    ),
    "chensu": (
        "我想再认识陈叙。他话不多，却把想练习说清楚这件事讲得很实在。",
        "三分钟单聊时，我想问一个具体问题，看看他会不会认真回答。",
    ),
}
CAST_FIRST_IMPRESSION_FALLBACKS.update({
    "luyao": ("我先记住陆遥。她把工作和来意讲得很清楚，也坦白自己并非从不犹豫。", "晚餐分工时，我想看看她会不会真的把改变主意说出来。"),
    "yecheng": ("我对叶澄有点好奇。她很自然地照顾场面，却先说了自己也想被询问。", "之后一起做事时，我想先问她一次真正的偏好。"),
    "tangli": ("我记住了唐梨。她说话很快，但提到别人说停时明显认真下来。", "如果有户外活动，我想看看她会怎样把选择权交回来。"),
    "wenxu": ("我想再认识温序。她承认会边说边改，却没有用分析躲开自己的来意。", "三分钟单聊时，我想给她一个不用准备完整答案的问题。"),
    "hechuan": ("我先记住贺川。他很会听，也主动说了自己不想只做倾听者。", "之后再聊时，我想把一个问题真正留给他回答。"),
    "peiran": ("我对裴然有点好奇。他把客厅带热了，也坦白自己在意热闹结束以后。", "场面安静时，我想看看他会不会仍然留在对话里。"),
    "lichuan": ("我记住了黎川。他很会组织大家，却直接说不想再一个人收尾。", "晚餐准备时，我想看看谁会主动和他分担。"),
    "qiaolan": ("我想再认识乔岚。她话不多，却把想练习先解释一句说得很实在。", "一起做事时，我想看看她会不会在行动前先问我。"),
})

STORY_OBJECTIVES = {
    "arrival-context": "选定你想怎样进入这段七天六夜的旅程",
    "villa-arrival": "走进酒店，用一个自然动作和八位嘉宾见面",
    "introductions": "在客厅完成一次姓名、公开背景、性格和来意都清楚的自我介绍",
    "cast-first-impressions": "听完其余七位嘉宾的介绍，留下一个以后可以被行动验证的第一印象",
    "icebreaker-choice": "选一位非主角嘉宾完成三分钟破冰，记住对方一件真实小事",
    "guided-chat": "先完成一次自然寒暄，再用一句可回答的话邀请对方一起准备晚餐",
    "team-up": "和破冰对象商量第一顿晚餐的具体分工",
    "anonymous-letter": "从三位非主角嘉宾中选择今晚最想继续认识的人发送匿名短信",
    "callback": "回收昨晚的选择，进入第二天",
}

DAY1_MEDIA_CONTRACT: dict[str, dict[str, Any]] = {
    "arrival-context": {"eventId": "day1.arrival-context", "assetId": "D1-A1-island-hotel-establish", "intent": "establish-island-journey"},
    "villa-arrival": {"eventId": "day1.villa-arrival", "assetId": "D1-A2-villa-entry", "intent": "enter-villa-and-meet-cast"},
    "introductions": {"eventId": "day1.introductions", "assetId": "D1-A3-cast-introductions", "intent": "camera-ready-self-introduction", "routingMode": "perspective"},
    "cast-first-impressions": {
        "eventId": "day1.cast-first-impressions",
        "assetId": "D1-A3B-cast-first-impressions",
        "intent": "hear-full-cast-and-seed-first-impression", "routingMode": "current-eight",
    },
    "icebreaker-choice": {"eventId": "day1.icebreaker-choice", "assetId": "D1-A4-icebreaker-selection", "intent": "choose-first-small-talk"},
    "guided-chat": {"eventId": "day1.guided-chat", "assetId": "D1-A5-guided-smalltalk", "intent": "guided-one-to-one-smalltalk"},
    "team-up": {
        "eventId": "day1.team-up", "assetId": "D1-A6-first-dinner-team", "intent": "first-dinner-cooperation",
        "variantRouting": "participants", "variantAssetIds": {"shenmo": "D1-A6-first-dinner-team--shenmo"},
    },
    "anonymous-letter": {
        "eventId": "day1.anonymous-letter", "assetId": "D1-A7-heart-message", "intent": "send-anonymous-heart-message",
        "variantRouting": "perspective", "variantAssetIds": {"jiangmi": "D1-A7-heart-message--jiangmi"},
    },
    "callback": {"eventId": "day2.morning-callback", "assetId": "D2-A1-memory-callback", "intent": "recall-choice-next-morning"},
}


def _load_json(name: str) -> dict[str, Any]:
    with (ROOT / "content" / name).open(encoding="utf-8") as source:
        return json.load(source)


APPROVED_RUNTIME_MEDIA_STATUSES = {"ready", "approved-runtime"}


def _runtime_asset_map() -> dict[str, dict[str, Any]]:
    try:
        package = json.loads((ROOT / "media" / "runtime-media-manifest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {str(item.get("id")): item for item in package.get("assets", []) if isinstance(item, dict) and item.get("id")}


def _asset_is_runtime_ready(asset: dict[str, Any]) -> bool:
    return bool(asset.get("path")) and asset.get("status") in APPROVED_RUNTIME_MEDIA_STATUSES


CARD_PACKAGE = _load_json("character_cards.v3.json")
PLAYER_GROUPS: dict[str, list[str]] = CARD_PACKAGE["playerGroups"]
CHARACTER_CARDS: list[dict[str, Any]] = CARD_PACKAGE["cards"]
CHARACTER_CARD_MAP = {card["id"]: card for card in CHARACTER_CARDS}
RUNTIME_ASSET_MAP = _runtime_asset_map()


def _public_character(card: dict[str, Any]) -> dict[str, Any]:
    psychology, voice = card["psychology"], card["voice"]
    card_video = str(card.get("video") or "")
    card_media_status = str(card.get("media", {}).get("status") or "")
    # The original eight cards predate the explicit media object; their
    # checked-in character-specific video is the approved legacy runtime.
    card_video_ready = bool(card_video) and (not card_media_status or card_media_status in APPROVED_RUNTIME_MEDIA_STATUSES)
    runtime_portrait = RUNTIME_ASSET_MAP.get(f"CHAR-{card['id']}-portrait", {})
    runtime_portrait_ready = _asset_is_runtime_ready(runtime_portrait)
    runtime_identity_cast = runtime_portrait.get("identityCast")
    runtime_portrait_identity_safe = bool(
        runtime_portrait_ready
        and isinstance(runtime_identity_cast, list)
        and [str(character_id) for character_id in runtime_identity_cast] == [card["id"]]
    )
    projected_video = str(runtime_portrait.get("path")) if runtime_portrait_identity_safe else (card_video if card_video_ready else "")
    facts = card.get("sourceProfile", {}).get("facts", {})
    raw_occupation = facts.get("occupation")
    occupation = str(raw_occupation).strip() if isinstance(raw_occupation, str) else ""
    if not occupation or any(marker in occupation for marker in ("待剧情", "待正式确认", "运行时职业待", "原稿为")):
        occupation = "职业待公开"
    raw_age = facts.get("age")
    age = raw_age if isinstance(raw_age, int) and raw_age > 0 else None
    return {
        "id": card["id"], "name": card["names"]["primary"], "mbti": card["mbti"],
        "tagline": card["tagline"], "accent": card["accent"], "portrait": card["portrait"],
        "video": projected_video, "age": age, "occupation": occupation,
        "gender": card.get("identity", {}).get("gender") or "未公开",
        "mediaStatus": "ready" if projected_video else (card.get("media", {}).get("status") or "planned"),
        "mediaFallbackKind": "dynamic-portrait" if projected_video else card.get("media", {}).get("fallbackKind"),
        "publicFacts": {"age": age, "occupation": occupation},
        "publicMask": "、".join(psychology["publicMask"]),
        "privateFear": psychology["fears"][0], "memorySeed": card["drives"]["stakes"],
        "voice": f"{voice['register']}；{voice['sentenceShape']}",
        "boundary": "；".join(psychology["boundaries"]),
        "quickPrompts": [shot["player"] for shot in card["fewShots"]],
        "independentInterest": card["drives"]["independentInterest"],
        "eventLabel": card["eventPolicy"]["label"],
    }


CHARACTERS = [_public_character(card) for card in CHARACTER_CARDS]
CHARACTER_MAP = {character["id"]: character for character in CHARACTERS}
LEGACY_CAST_IDS = tuple(card["id"] for card in CHARACTER_CARDS[:8])
ROSTER_GENDERS = ("男性", "女性")
MEDIA_ROTATION_ANCHORS = {
    "M-A-chengye": "chengye", "M-B-hechuan": "hechuan",
    "F-A-jiangmi": "jiangmi", "F-B-luyao": "luyao",
}


def _stable_index(seed: str, namespace: str, size: int) -> int:
    if size <= 0:
        return 0
    digest = sha256(f"{seed}:{namespace}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def select_run_cast(perspective_character_id: str, seed: str) -> list[str]:
    """Choose one persisted eight-person season from the sixteen-card library.

    The selected protagonist and their other-gender MBTI counterpart always
    appear together.  Six more distinct MBTI types are selected with a stable
    seed, three men and three women, yielding a balanced four/four cast.
    """
    if perspective_character_id not in CHARACTER_CARD_MAP:
        raise ValueError("观察人物不存在")
    perspective = CHARACTER_CARD_MAP[perspective_character_id]
    same_type = [
        card for card in CHARACTER_CARDS
        if card["mbti"] == perspective["mbti"] and card["id"] != perspective_character_id
        and card.get("identity", {}).get("gender") != perspective.get("identity", {}).get("gender")
    ]
    if not same_type:
        raise ValueError("该 MBTI 尚未配置另一性别角色")
    counterpart = sorted(same_type, key=lambda card: card["id"])[0]
    other_types = sorted({card["mbti"] for card in CHARACTER_CARDS if card["mbti"] != perspective["mbti"]})
    omitted = other_types[_stable_index(seed, "omitted-mbti", len(other_types))]
    included_types = [mbti for mbti in other_types if mbti != omitted]
    included_types.sort(key=lambda mbti: sha256(f"{seed}:mbti:{mbti}".encode()).hexdigest())
    male_types = set(included_types[:3])
    selected = [perspective_character_id, counterpart["id"]]
    for mbti in included_types:
        gender = "男性" if mbti in male_types else "女性"
        options = [card for card in CHARACTER_CARDS if card["mbti"] == mbti and card.get("identity", {}).get("gender") == gender]
        if not options:
            raise ValueError(f"{mbti} 尚未配置{gender}角色")
        selected.append(sorted(options, key=lambda card: card["id"])[0]["id"])
    return selected


MEDIA_ROTATION_SELECTION_BUCKETS: dict[str, tuple[str, ...]] = {
    "F-A-jiangmi": ("ENFP", "ESFJ", "ISFJ", "ESTP"),
    "F-B-luyao": ("INTJ", "INFJ", "INTP", "ISTP"),
    "M-A-chengye": ("ESTP", "ISTP", "ESFJ", "ISFJ"),
    "M-B-hechuan": ("ENFP", "INFJ", "INTJ", "INTP"),
}


def normalize_character_gender(value: Any) -> str:
    """Normalize production-manifest gender labels to the runtime contract."""
    normalized = str(value or "").strip().lower()
    return {
        "female": "女性", "woman": "女性", "f": "女性", "女性": "女性", "女": "女性",
        "male": "男性", "man": "男性", "m": "男性", "男性": "男性", "男": "男性",
    }.get(normalized, "")


def media_rotation_for(
    perspective_character_id: str,
    seed: str,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Choose a same-gender reusable video scheme for one event.

    ``selectionBucket`` determines the character's preferred scheme. Event
    routing then uses a stable hash of ``playerCharacterId + eventId`` to
    alternate between the two same-gender schemes. This keeps reloads
    deterministic without showing one lead image for the whole run.
    ``seed`` remains in the signature for snapshot compatibility; R6 event
    routing deliberately does not depend on the randomly generated run id.
    """
    del seed
    if perspective_character_id not in CHARACTER_MAP:
        raise ValueError("媒体视角人物不存在")
    character = CHARACTER_MAP[perspective_character_id]
    gender = character["gender"]
    mbti = character["mbti"]
    slots = ("M-A-chengye", "M-B-hechuan") if gender == "男性" else ("F-A-jiangmi", "F-B-luyao")
    preferred_index = next(
        (index for index, slot_id in enumerate(slots) if mbti in MEDIA_ROTATION_SELECTION_BUCKETS[slot_id]),
        0,
    )
    event_bucket = _stable_index(perspective_character_id, f"media-rotation:{event_id}", len(slots)) if event_id else 0
    slot = slots[(preferred_index + event_bucket) % len(slots)]
    return {
        "slot": slot,
        "leadGender": gender,
        "anchorCharacterId": MEDIA_ROTATION_ANCHORS[slot],
        "selectionBucket": list(MEDIA_ROTATION_SELECTION_BUCKETS[slot]),
        "eventId": event_id,
    }


def active_cast_ids(snapshot: dict[str, Any]) -> list[str]:
    perspective_id = str(snapshot.get("player", {}).get("perspectiveCharacterId") or "")
    cast = snapshot.get("castIds")
    if isinstance(cast, list):
        normalized = [str(character_id) for character_id in cast if str(character_id) in CHARACTER_MAP]
        if len(normalized) == 8 and len(set(normalized)) == 8 and perspective_id in normalized:
            return normalized
    if perspective_id in LEGACY_CAST_IDS:
        return list(LEGACY_CAST_IDS)
    return select_run_cast(perspective_id, str(snapshot.get("runId") or perspective_id))

NODES: dict[str, dict[str, Any]] = {
    "arrival-context": {
        "chapter": "DAY 1 · 旅程开始", "eyebrow": "心动之旅 / 序章",
        "title": "七天六夜，从一句你好开始", "speaker": "节目旁白",
        "text": "八位嘉宾将在海岛酒店共同生活七天六夜。一起吃饭、出行、做游戏，也一起面对心动、犹豫和误会。靠近别人，也是在重新认识自己。",
        "action": "海面掠过傍晚的光，镜头缓缓靠近亮灯的海岛酒店。",
        "cinematic": "/media/video/D1-A1-island-hotel-establish.mp4",
        "mediaCue": "海岛酒店远景、车辆驶近，八位嘉宾尚未见面的旅程序章",
        "choices": [
            {"id": "context-meet", "intentId": "context.meet-people", "label": "先认真认识眼前的每一个人", "hint": "不急着贴标签，让相处给出答案", "next": "villa-arrival", "patch": {"flags.relationshipFocus": 1}},
            {"id": "context-live", "intentId": "context.share-life", "label": "从一起生活的小事慢慢靠近", "hint": "把衣食住行当成了解彼此的开始", "next": "villa-arrival", "patch": {"flags.reciprocity": 1}},
            {"id": "context-self", "intentId": "context.know-self", "label": "也想借这趟旅程重新认识自己", "hint": "允许心动，也允许改变原来的判断", "next": "villa-arrival", "patch": {"flags.clarity": 1}},
        ],
    },
    "villa-arrival": {
        "chapter": "DAY 1 · 抵达海岛", "eyebrow": "心动酒店 / 17:30",
        "title": "欢迎来到《心动之旅》", "speaker": "节目旁白",
        "text": "八位嘉宾将在海岛酒店共同生活七天六夜。从今天起，做饭、出行、游戏和每一次相处，都可能碰撞出意想不到的火花。",
        "action": "车辆停在酒店门前，八只行李箱陆续被搬下车。",
        "cinematic": "/media/video/E01-arrival-reveal.mp4",
        "mediaCue": "八位嘉宾先后抵达海岛酒店、搬运行李并第一次看见彼此",
        "gameBrief": {
            "name": "七天六夜，从一句你好开始",
            "format": "白天一起生活并完成节目组安排，晚上可以把一条心动短信发给当天最想继续认识的人。",
            "winCondition": "这里没有积分榜。旅程结束时，你可以走向一位还想继续了解的人，也可以带着更清楚的自己离开。",
            "strategyPrompt": "刚走进酒店，你准备先做什么？",
            "strategyOptions": ["先帮身边的人拿行李", "先向客厅里的大家打招呼", "先记住每个人的名字和位置"],
        },
        "choices": [
            {"id": "arrival-help-luggage", "intentId": "arrival.offer-help", "label": "接过身边的一只行李箱", "hint": "用一个自然的小动作打开第一句话", "next": "introductions", "patch": {"flags.courage": 1, "flags.publicImpression": 1}},
            {"id": "arrival-greet-room", "intentId": "arrival.greet-group", "label": "先走进客厅向大家问好", "hint": "让所有人先记住你的名字", "next": "introductions", "patch": {"flags.courage": 2}},
            {"id": "arrival-observe-names", "intentId": "arrival.observe", "label": "慢一步，先记住谁在做什么", "hint": "你会带着更多生活细节进入破冰", "next": "introductions", "patch": {"flags.observation": 2}},
        ],
    },
    "introductions": {
        "chapter": "DAY 1 · 初次见面", "eyebrow": "酒店客厅 / 18:05",
        "title": "八个名字，第一次被彼此叫出来", "speaker": "节目旁白",
        "text": "大家围着客厅坐下。节目组请每个人说说自己是谁、做什么工作，以及为什么愿意把七天时间交给一群陌生人。现在轮到你了。",
        "action": "镜头掠过围坐的嘉宾，最后停在你的座位前。",
        "mediaCue": "海岛别墅客厅内八位嘉宾围坐、轮流自然自我介绍",
        "choices": [
            {"id": "intro-clear", "intentId": "introduction.clear", "introductionMode": "camera-full", "label": "认真介绍姓名、工作和来意", "hint": "信息清楚，给别人一个容易接住的话题", "next": "cast-first-impressions", "patch": {"flags.clarity": 2}},
            {"id": "intro-question", "intentId": "introduction.invite", "introductionMode": "living-room-keepsake", "label": "介绍完自己，再把问题抛给大家", "hint": "主动制造一次轻松的来回", "next": "cast-first-impressions", "patch": {"flags.reciprocity": 2}},
            {"id": "intro-honest", "intentId": "introduction.honest", "introductionMode": "contrast-full", "label": "承认有点紧张，也说一句真心话", "hint": "不追求完美，先让人看见真实的一面", "next": "cast-first-impressions", "patch": {"flags.relationshipFocus": 2}},
        ],
    },
    "cast-first-impressions": {
        "chapter": "DAY 1 · 初见回声", "eyebrow": "酒店客厅 / 18:18",
        "title": "最后一个名字说完，客厅才真的安静下来", "speaker": "节目旁白",
        "text": "你说完后没有立刻起身。其余七位嘉宾继续介绍：有人把工作和来意讲得干脆，有人承认面对镜头会紧张，也有人把问题抛回给大家。最后一个名字落下时，你已经悄悄记住了一个人。这个第一印象，会在晚餐分工和今晚的短信里被重新验证。",
        "textBeats": [
            "你说完后没有立刻起身，其余七位嘉宾继续介绍自己。",
            "有人讲得干脆，有人承认紧张，也有人把问题重新抛回给大家。",
            "最后一个名字落下时，你已经悄悄记住了一个人。",
            "这个第一印象，会在晚餐分工和今晚的短信里被重新验证。",
        ],
        "action": "镜头依次切过其余七人的表情，最后回到你停在膝上的手。",
        "mediaCue": "主角听完其余七位嘉宾的自然自我介绍，目光在几位嘉宾之间停留并形成第一印象",
        "choices": [
            {
                "id": "impression-listener", "intentId": "impression.remember-listener",
                "impressionKind": "listening", "label": "先记住那个认真听完所有人介绍的人",
                "hint": "这份安静是真诚还是谨慎，要等下一次相处验证",
                "next": "icebreaker-choice", "patch": {"flags.observation": 1},
            },
            {
                "id": "impression-care", "intentId": "impression.notice-care",
                "impressionKind": "care", "label": "留意那个一直替别人把话接住的人",
                "hint": "照顾场面的人，也可能希望有人先问问他自己",
                "next": "icebreaker-choice", "patch": {"flags.reciprocity": 1},
            },
            {
                "id": "impression-contrast", "intentId": "impression.follow-contrast",
                "impressionKind": "contrast", "label": "记住那个第一眼和自我介绍最不一样的人",
                "hint": "先把反差留在心里，之后用行动而不是标签确认",
                "next": "icebreaker-choice", "patch": {"flags.relationshipFocus": 1},
            },
        ],
    },
    "icebreaker-choice": {
        "chapter": "DAY 1 · 破冰时刻", "eyebrow": "酒店公共区 / 18:25",
        "title": "三张场景卡，选一个人聊三分钟", "speaker": "节目组",
        "text": "桌上有三张卡，分别写着客厅、露台和行李区。每张卡都对应一位你还没单独聊过的嘉宾。选一张，就去那个地方找到卡片上的人，从刚才的自我介绍或眼前的小事聊起。三分钟后回到客厅，准确说出对方亲口告诉你的一件小事，对方点头或补充，就算完成。",
        "textBeats": [
            "桌上有三张卡：客厅、露台和行李区，每张都对应一位嘉宾。",
            "选一张，就去那个地方找到卡片上的人，聊够三分钟。",
            "可以从刚才的自我介绍问起，也可以从眼前正在做的小事开口。",
            "回来后说出对方亲口告诉你的一件小事；对方点头或补充，就算完成。",
        ],
        "action": "三张写着地点和嘉宾姓名的生活场景卡被翻到桌面中央。",
        "mediaCue": "嘉宾在客厅抽取生活场景卡并分散到厨房、露台和行李区破冰",
        "gameBrief": {
            "name": "三分钟，记住一件小事",
            "format": "三张卡分别写着一个地点和一位嘉宾。选卡后去对应地点，和那位嘉宾单独聊三分钟；卡片不是配对结果，也没有隐藏谜题。",
            "winCondition": "回到客厅后，说出对方亲口告诉你的一件真实小事。对方点头确认或主动补充，就算你认真听见了。",
            "strategyPrompt": "看清每张卡上的人和开场方式，再选你愿意真的聊三分钟的那一张。",
            "strategyOptions": ["问刚才自我介绍里没展开的一句", "从对方眼前正在做的小事开口", "先交换为什么来参加节目的真实原因"],
        },
        "choices": [
            {"id": "break-help", "intentId": "icebreaker.offer-help", "label": "去帮一位嘉宾整理手边的东西", "hint": "从共同做一件小事开始认识", "next": "guided-chat", "patch": {"flags.publicImpression": 1}},
            {"id": "break-introduce", "intentId": "icebreaker.exchange-names", "label": "走向一位嘉宾，先交换姓名", "hint": "从最普通的一声你好开始", "next": "guided-chat", "patch": {"flags.courage": 1}},
            {"id": "break-notice", "intentId": "icebreaker.notice-detail", "label": "问问一位嘉宾刚才在忙什么", "hint": "用你真正看到的细节打开话题", "next": "guided-chat", "patch": {"flags.observation": 1}},
        ],
    },
    "guided-chat": {
        "chapter": "DAY 1 · 第一次单独说话", "eyebrow": "破冰倒计时 / 18:31",
        "title": "先认识对方，再谈要不要同行", "speaker": "节目提示",
        "text": "你已经选好了这次破冰的对象。先从姓名、来到节目的原因或眼前的小事聊起；完成一次真实来回后，再决定怎样提出今晚的组队邀请。",
        "action": "对应嘉宾的头像亮起，正在等你开口。",
        "requiresGuidedInteraction": True,
        "mediaCue": "指定嘉宾在生活场景中停下动作，转身和玩家开始第一次单独交谈",
        "choices": [
            {"id": "chat-team-direct", "intentId": "team.invite-direct", "label": "直接邀请对方和你组队", "hint": "态度清楚，也给对方拒绝的空间", "next": "team-up", "patch": {"flags.taskFocus": 1}},
            {"id": "chat-team-together", "intentId": "team.decide-together", "label": "先问对方想做什么，再一起决定", "hint": "把分工变成一次共同选择", "next": "team-up", "patch": {"flags.reciprocity": 2}},
            {"id": "chat-team-light", "intentId": "team.keep-light", "label": "只约定完成今晚这一件事", "hint": "降低压力，给关系留下继续了解的空间", "next": "team-up", "patch": {"flags.clarity": 1}},
        ],
    },
    "team-up": {
        "chapter": "DAY 1 · 第一次组队", "eyebrow": "晚餐准备 / 19:10",
        "title": "第一顿晚餐，是第一次一起做事", "speaker": "节目旁白",
        "text": "今晚不比输赢。你和刚认识的搭档要在晚餐前完成一项生活分工。一起做事时的照顾、坚持和小摩擦，往往比自我介绍更接近真实。",
        "action": "厨房、采购桌和露台布置区同时亮起任务灯。",
        "mediaCue": "双人搭档在厨房备菜、整理餐桌或核对采购清单，其他嘉宾从旁经过互动",
        "gameBrief": {
            "name": "第一顿晚餐搭档",
            "format": "你和破冰对象从备菜、布置餐桌、核对饮品中选一项，在晚餐开始前共同完成。",
            "winCondition": "两个人都完成自己答应的部分，并在结束时说清下一次希望怎样合作，就算完成。",
            "strategyPrompt": "你准备怎样和搭档配合？",
            "strategyOptions": ["先分工，各自做好一半", "边做边商量，随时交换任务", "先承担麻烦的部分，再请对方补位"],
        },
        "choices": [
            {"id": "team-split", "intentId": "team.split-work", "label": "先把任务拆开，各自负责一半", "hint": "效率更高，也能看见彼此是否守约", "next": "anonymous-letter", "patch": {"flags.clarity": 1, "flags.taskFocus": 1}},
            {"id": "team-cooperate", "intentId": "team.work-together", "label": "留在同一区域，边做边商量", "hint": "有更多相处时间，也可能暴露小摩擦", "next": "anonymous-letter", "patch": {"flags.relationshipFocus": 1, "flags.reciprocity": 1}},
            {"id": "team-volunteer", "intentId": "team.take-hard-part", "label": "先接下更麻烦的那一部分", "hint": "用行动表达诚意，但不替对方包办", "next": "anonymous-letter", "patch": {"flags.courage": 1, "flags.publicImpression": 1}},
        ],
    },
    "anonymous-letter": {
        "chapter": "DAY 1 · 心动短信", "eyebrow": "心动信箱 / 22:30",
        "title": "今晚，你还想继续认识谁？", "speaker": "节目旁白",
        "text": "睡前，每个人可以把一条不署名的心动短信发给今天最想继续了解的人。节目只公布每个人收到几条，不公布发送者。你的一条短信，不等于承诺，只代表今天的真实选择。",
        "action": "八部手机同时亮起，只留下一个收信人的位置。",
        "cinematic": "/media/video/E01-anonymous-letter.mp4", "characterChoice": True, "choices": [],
        "mediaCue": "夜晚卧室与走廊交叉剪辑，嘉宾独自编辑匿名心动短信并等待提示音",
    },
    "callback": {
        "chapter": "DAY 2 · 清晨回声", "eyebrow": "海边早餐 / 07:18",
        "title": "昨晚的一句话，留到了今天", "speaker": "节目旁白",
        "text": "短信没有替任何人决定关系，却让今天的座位、目光和下一次邀请有了新的方向。七天六夜才刚刚开始。",
        "action": "清晨餐桌旁，有人把相邻的椅子轻轻拉开。",
        "mediaCue": "清晨海边早餐桌、手机短信提示与昨晚收信对象的自然回望",
        "isEnding": True, "choices": [],
    },
}

DAY1_SCRIPT_NODE_IDS = tuple(NODES)
LEGACY_NODE_MAP = {
    "first-look": "introductions",
    "private-window": "guided-chat",
    "event-reveal": "team-up",
    "arrival": "arrival-context",
    "heart-message": "anonymous-letter",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def player_group(mbti: str) -> str:
    return next((group for group, types in PLAYER_GROUPS.items() if mbti in types), "diplomats")


def _empty_axes() -> dict[str, int]:
    return {axis: 0 for axis in RELATIONSHIP_AXES}


def split_story_beats(text: str) -> list[str]:
    """Split visible prose into a small manual-reading sequence without changing its meaning."""
    parts = [part.strip() for part in re.findall(r"[^。！？!?；;]+[。！？!?；;]?", str(text or "")) if part.strip()]
    if not parts:
        return []
    beats: list[str] = []
    for part in parts:
        if beats and (len(part) < 18 or len(beats[-1]) < 18) and len(beats[-1]) + len(part) <= 60:
            beats[-1] += part
        else:
            beats.append(part)
    while len(beats) > 4:
        beats[-2] += beats.pop()
    return beats


def _fallback_target_ids(perspective_character_id: str, cast_ids: list[str] | None = None) -> list[str]:
    """Return three deterministic non-self people for the first guided exchange."""
    cast_order = [character_id for character_id in (cast_ids or list(LEGACY_CAST_IDS)) if character_id in CHARACTER_MAP]
    if perspective_character_id not in cast_order:
        cast_order = [perspective_character_id, *cast_order]
    first_four, second_four = cast_order[:4], cast_order[4:]
    preferred = second_four if perspective_character_id in first_four else first_four
    ordered = [*preferred, *(character_id for character_id in cast_order if character_id not in preferred)]
    return [character_id for character_id in ordered if character_id != perspective_character_id][:3]


def _asset_identity_cast(asset: dict[str, Any]) -> list[str]:
    cast = asset.get("identityCast")
    if not isinstance(cast, list):
        return []
    return [str(character_id) for character_id in cast if str(character_id) in CHARACTER_MAP]


def _identity_card(character_id: str) -> dict[str, Any]:
    character = CHARACTER_MAP[character_id]
    return {
        "characterId": character_id,
        "name": character["name"],
        "mbti": character["mbti"],
        "age": character.get("age"),
        "occupation": character.get("occupation") or "职业待公开",
        "tagline": character["tagline"],
    }


def _identity_timeline_for_asset(asset: dict[str, Any], identity_cast: list[str]) -> list[dict[str, Any]]:
    """Return a label timeline that never names somebody outside the clip.

    Reviewed composites list identities in edit order. Older manifests did not
    include per-person timecodes, so divide those clips into equal sections and
    show each plate for at most three seconds. This keeps the label on the face
    it describes instead of cycling independently of the edit.
    """
    declared = asset.get("identityTimeline")
    if isinstance(declared, list):
        safe_declared: list[dict[str, Any]] = []
        for item in declared:
            if not isinstance(item, dict) or str(item.get("characterId") or "") not in identity_cast:
                continue
            try:
                start = max(0.0, float(item.get("startSeconds", 0)))
                end = float(item.get("endSeconds", start))
            except (TypeError, ValueError):
                continue
            if end > start:
                safe_declared.append({"characterId": str(item["characterId"]), "startSeconds": start, "endSeconds": end})
        if safe_declared:
            return safe_declared
    if len(identity_cast) < 2 or asset.get("sourceType") != "local-composite":
        return []
    try:
        duration = float(asset.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        return []
    segment = duration / len(identity_cast)
    return [
        {
            "characterId": character_id,
            "startSeconds": round(index * segment, 3),
            "endSeconds": round(min((index * segment) + 3.0, (index + 1) * segment), 3),
        }
        for index, character_id in enumerate(identity_cast)
    ]


def resolve_identity_safe_media(
    base_asset_id: str,
    perspective_character_id: str,
    participant_ids: list[str] | None = None,
    *,
    routing_mode: str = "perspective",
    fixed_cast_ids: list[str] | None = None,
    current_cast_ids: list[str] | None = None,
    rotation: dict[str, Any] | None = None,
    asset_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve only footage whose reviewed identity cast covers the live scene.

    A generated clip is never considered interchangeable merely because its
    event matches.  It must also name the selected protagonist and every
    committed participant in ``identityCast``.  Until that exact variant has
    passed review, the selected protagonist's existing dynamic portrait is the
    safe runtime fallback; the old Jiangmi event master is never substituted.
    """
    if perspective_character_id not in CHARACTER_MAP:
        raise ValueError("媒体视角人物不存在")
    asset_map = asset_map if asset_map is not None else _runtime_asset_map()
    cast_order = [character_id for character_id in (current_cast_ids or list(CHARACTER_MAP)) if character_id in CHARACTER_MAP]
    if perspective_character_id not in cast_order:
        cast_order.insert(0, perspective_character_id)
    cast_set = set(cast_order)
    participants: list[str] = []
    participant_out_of_cast = False
    for character_id in participant_ids or []:
        if character_id in CHARACTER_MAP and character_id not in cast_set:
            participant_out_of_cast = True
            continue
        if character_id in CHARACTER_MAP and character_id != perspective_character_id and character_id not in participants:
            participants.append(character_id)
    order_index = {character_id: index for index, character_id in enumerate(cast_order)}
    if participant_out_of_cast:
        routing_mode = "perspective"
        required_cast = [perspective_character_id]
        canonical_asset_id = f"{base_asset_id}--p-{perspective_character_id}"
    elif routing_mode == "participant-pov" and participants:
        required_cast = [participants[0]]
        canonical_asset_id = f"{base_asset_id}--npc-{participants[0]}"
    elif routing_mode == "unordered-pair" and participants:
        pair = sorted({perspective_character_id, participants[0]}, key=lambda item: order_index[item])
        required_cast = pair
        canonical_asset_id = f"{base_asset_id}--pair-{'-'.join(pair)}"
    elif routing_mode == "fixed-cast":
        requested_fixed = [character_id for character_id in fixed_cast_ids or participants if character_id in CHARACTER_MAP]
        fixed = [character_id for character_id in requested_fixed if character_id in cast_set]
        if len(fixed) != len(requested_fixed):
            routing_mode = "perspective"
            required_cast = [perspective_character_id]
            canonical_asset_id = f"{base_asset_id}--p-{perspective_character_id}"
        else:
            required_cast = list(dict.fromkeys(fixed)) or [perspective_character_id]
            canonical_asset_id = f"{base_asset_id}--fixed-{'-'.join(required_cast)}"
    elif routing_mode == "current-eight":
        required_cast = cast_order
        canonical_asset_id = f"{base_asset_id}--group-current-eight"
    else:
        routing_mode = "perspective"
        required_cast = [perspective_character_id]
        canonical_asset_id = f"{base_asset_id}--p-{perspective_character_id}"

    # New R5 semantic IDs come first. Directed R4-style IDs remain readable
    # during migration, but identity metadata must prove the exact same cast.
    directed_cast = [perspective_character_id, *participants]
    legacy_directed = f"{base_asset_id}--{'--'.join(directed_cast)}"
    legacy_perspective = f"{base_asset_id}--{perspective_character_id}"
    candidate_ids = list(dict.fromkeys([canonical_asset_id, legacy_directed, legacy_perspective, base_asset_id]))

    selected_asset_id = ""
    selected_asset: dict[str, Any] = {}
    for candidate_id in candidate_ids:
        candidate = asset_map.get(candidate_id, {})
        if not _asset_is_runtime_ready(candidate):
            continue
        identity_cast = _asset_identity_cast(candidate)
        if set(identity_cast) == set(required_cast) and len(identity_cast) == len(required_cast):
            selected_asset_id, selected_asset = candidate_id, candidate
            break

    # The formal version may reuse one of four approved reenactment sets (two
    # per protagonist gender) instead of generating every event for all 16
    # identities. Exact-cast footage above always wins. A rotation clip is
    # accepted only when every visible person belongs to this season's eight-
    # person cast; otherwise it would introduce a stranger under a real name.
    rotation_asset_id = ""
    selected_rotation_slot = ""
    selected_rotation_cast: list[str] = []
    player_gender = CHARACTER_MAP[perspective_character_id]["gender"]
    allowed_rotation_slots = ("M-A-chengye", "M-B-hechuan") if player_gender == "男性" else ("F-A-jiangmi", "F-B-luyao")
    rotation_slot = str((rotation or {}).get("slot") or "")
    rotation_anchor = str((rotation or {}).get("anchorCharacterId") or "")
    rotation_gender = normalize_character_gender((rotation or {}).get("leadGender"))
    rotation_request_is_valid = bool(
        rotation
        and rotation_gender == player_gender
        and rotation_slot in allowed_rotation_slots
        and MEDIA_ROTATION_ANCHORS.get(rotation_slot) == rotation_anchor
        and rotation_anchor in CHARACTER_MAP
        and CHARACTER_MAP[rotation_anchor]["gender"] == player_gender
    )
    if not selected_asset_id and rotation_request_is_valid:
        ordered_slots = [rotation_slot, *(slot for slot in allowed_rotation_slots if slot != rotation_slot)]
        for candidate_slot in ordered_slots:
            candidate_anchor = MEDIA_ROTATION_ANCHORS[candidate_slot]
            if candidate_anchor not in cast_set:
                continue
            proposed_rotation_id = f"{base_asset_id}--rotation-{candidate_slot}"
            candidate = asset_map.get(proposed_rotation_id, {})
            declared_gender = normalize_character_gender(candidate.get("leadGender"))
            if not _asset_is_runtime_ready(candidate) or declared_gender != player_gender:
                continue
            candidate_cast = _asset_identity_cast(candidate) or [candidate_anchor]
            if candidate_anchor not in candidate_cast or not set(candidate_cast).issubset(cast_set):
                continue
            selected_asset_id, selected_asset = proposed_rotation_id, candidate
            rotation_asset_id = proposed_rotation_id
            selected_rotation_slot = candidate_slot
            selected_rotation_cast = candidate_cast
            break

    planned_asset_id = canonical_asset_id
    if selected_asset_id:
        identity_cast = _asset_identity_cast(selected_asset)
        visible_cast = selected_rotation_cast if rotation_asset_id else (identity_cast or required_cast)
        identity_timeline = _identity_timeline_for_asset(selected_asset, visible_cast)
        return {
            "assetId": selected_asset_id,
            "baseAssetId": base_asset_id,
            "variantForCharacterId": perspective_character_id if selected_asset_id != base_asset_id else None,
            "src": selected_asset["path"],
            "poster": selected_asset.get("poster") or "",
            "plannedSrc": f"/media/video/{planned_asset_id}.mp4",
            "plannedPoster": f"/media/posters/{planned_asset_id}.jpg",
            "available": True,
            "status": "ready",
            "selectionReason": "approved-gender-rotation" if rotation_asset_id else "reviewed-identity-cast",
            "routingMode": "gender-rotation" if rotation_asset_id else routing_mode,
            "rotationSlot": selected_rotation_slot if rotation_asset_id else None,
            "rotationSelectionBucket": list(MEDIA_ROTATION_SELECTION_BUCKETS[selected_rotation_slot]) if rotation_asset_id else None,
            "rotationEventId": rotation.get("eventId") if rotation_asset_id and rotation else None,
            "leadGender": player_gender,
            "requiredIdentityCast": required_cast,
            "identityCast": visible_cast,
            "identityCards": [_identity_card(character_id) for character_id in visible_cast if character_id in CHARACTER_MAP],
            "identityTimeline": deepcopy(identity_timeline),
            "fallback": {
                "kind": "dynamic-portrait" if CHARACTER_MAP[perspective_character_id]["video"] else "static-character-placeholder",
                "characterId": perspective_character_id,
                "src": CHARACTER_MAP[perspective_character_id]["video"],
                "poster": CHARACTER_MAP[perspective_character_id]["portrait"],
            },
        }

    # A missing event or participant clip always falls back to the selected
    # protagonist.  Showing a different NPC portrait can silently cross the
    # player's selected gender and falsely imply that person is the viewpoint.
    fallback_character_id = perspective_character_id
    portrait_asset_id = f"CHAR-{fallback_character_id}-portrait"
    portrait_asset = asset_map.get(portrait_asset_id, {})
    portrait_src = str(portrait_asset.get("path") or CHARACTER_MAP[fallback_character_id]["video"])
    portrait_poster = CHARACTER_MAP[fallback_character_id]["portrait"]
    return {
        "assetId": portrait_asset_id,
        "baseAssetId": base_asset_id,
        "variantForCharacterId": fallback_character_id,
        "src": portrait_src,
        "poster": portrait_poster,
        "plannedSrc": f"/media/video/{planned_asset_id}.mp4",
        "plannedPoster": f"/media/posters/{planned_asset_id}.jpg",
        "available": bool(portrait_src),
        "status": "identity-safe-fallback",
        "selectionReason": "exact-event-variant-awaiting-review",
        "routingMode": routing_mode,
        "rotationSlot": rotation_slot if rotation_request_is_valid else None,
        "rotationSelectionBucket": rotation.get("selectionBucket") if rotation_request_is_valid and rotation else None,
        "rotationEventId": rotation.get("eventId") if rotation_request_is_valid and rotation else None,
        "leadGender": player_gender,
        "rotationPlannedAssetId": f"{base_asset_id}--rotation-{rotation_slot}" if rotation_request_is_valid else None,
        "audioAvailable": False,
        "requiredIdentityCast": required_cast,
        "identityCast": [fallback_character_id],
        "identityCards": [_identity_card(fallback_character_id)],
        "identityTimeline": [{"characterId": fallback_character_id, "startSeconds": 0, "endSeconds": 3}],
        "fallback": {
            "kind": "dynamic-portrait" if portrait_src else "static-character-placeholder",
            "characterId": fallback_character_id,
            "src": portrait_src,
            "poster": portrait_poster,
        },
    }


def day1_media_context(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project an engine-owned media cue; model-written copy cannot alter asset routing."""
    node_id = state["nodeId"]
    blueprint = NODES[node_id]
    contract = DAY1_MEDIA_CONTRACT[node_id]
    guided_id = state.get("guidedTargetCharacterId")
    perspective_id = state["player"]["perspectiveCharacterId"]
    cast_ids = active_cast_ids(state)
    participant_ids: list[str] = []
    if node_id in {"guided-chat", "team-up"} and guided_id:
        participant_ids.append(guided_id)
    if node_id == "callback":
        callback_character_id = state.get("letterRecipientId") or state.get("focusCharacterId") or guided_id
        if callback_character_id:
            participant_ids.append(callback_character_id)
    routing_mode = str(contract.get("routingMode") or {
        "guided-chat": "participant-pov",
        "team-up": "unordered-pair",
        "callback": "participant-pov",
    }.get(node_id, "perspective"))
    media = resolve_identity_safe_media(
        contract["assetId"],
        perspective_id,
        participant_ids,
        routing_mode=routing_mode,
        current_cast_ids=cast_ids,
        rotation=media_rotation_for(
            perspective_id,
            str(state.get("runId") or perspective_id),
            contract["assetId"],
        ),
    )
    return {
        "eventId": contract["eventId"],
        "intent": contract["intent"],
        "cue": blueprint.get("mediaCue") or "恋综现场的自然过场",
        **media,
        "allowedChoiceIntentIds": [choice["intentId"] for choice in blueprint.get("choices", [])],
    }


def build_fallback_script_flavor(perspective_character_id: str, cast_ids: list[str] | None = None) -> dict[str, Any]:
    """Natural authored fallback; IDs and patches always come from ``NODES``."""
    nodes: dict[str, Any] = {}
    for node_id, blueprint in NODES.items():
        nodes[node_id] = {
            "title": blueprint["title"], "text": blueprint["text"],
            "textBeats": deepcopy(blueprint.get("textBeats") or split_story_beats(blueprint["text"])),
            "speakerId": "program" if blueprint["speaker"] == "节目组" else "narrator",
            "action": blueprint.get("action", ""),
            "choices": [
                {"id": choice["id"], "label": choice["label"], "hint": choice["hint"], "targetCharacterId": None}
                for choice in blueprint.get("choices", [])
            ],
        }
    targets = _fallback_target_ids(perspective_character_id, cast_ids)
    icebreaker_copy = [
        (f"选客厅卡，去问{CHARACTER_MAP[targets[0]]['name']}刚才没展开的参加原因", "姓名写在卡上；从自我介绍里没说完的一句接着聊"),
        (f"选露台卡，和{CHARACTER_MAP[targets[1]]['name']}交换这七天最想体验的事", "问题容易回答，也能听见对方真实的期待"),
        (f"选行李区卡，先问{CHARACTER_MAP[targets[2]]['name']}要不要搭把手放行李", "从眼前能一起完成的小事开口，不必硬找话题"),
    ]
    for choice, target_id, copy in zip(nodes["icebreaker-choice"]["choices"], targets, icebreaker_copy):
        choice.update({"label": copy[0], "hint": copy[1], "targetCharacterId": target_id})
    for choice, target_id in zip(nodes["cast-first-impressions"]["choices"], targets):
        label, hint = CAST_FIRST_IMPRESSION_FALLBACKS[target_id]
        choice.update({"label": label, "hint": hint, "targetCharacterId": target_id})
    intro_copy = INTRODUCTION_FALLBACKS[perspective_character_id]
    for choice in nodes["introductions"]["choices"]:
        label, hint = intro_copy[choice["id"]]
        choice.update({"label": label, "hint": hint, "introductionMode": INTRODUCTION_MODES[choice["id"]]})
    nodes["introductions"]["text"] = (
        "大家围着客厅坐下，轮流说出姓名、公开背景和来到这里的原因。现在镜头来到你："
        "不用准备漂亮答案，让陌生人先认识一个真实、具体的你。"
    )
    return {
        "schemaVersion": 1, "source": "fallback", "perspectiveCharacterId": perspective_character_id,
        "generatedAt": utc_now(), "nodes": nodes,
    }


def create_snapshot(user_mbti: str = "INFP", perspective_character_id: str | None = None) -> dict[str, Any]:
    if perspective_character_id not in CHARACTER_MAP:
        perspective_character_id = CHARACTER_CARDS[0]["id"]
    run_id = str(uuid4())
    cast_ids = select_run_cast(perspective_character_id, run_id)
    relationships = {character_id: _empty_axes() for character_id in cast_ids}
    flags = {key: 0 for key in ("heat", "clarity", "publicImpression", "courage", "priorityChoice", "observation", "taskFocus", "relationshipFocus", "reciprocity", "eventLinked", "acceptedEvent")}
    snapshot = {
        "runId": run_id, "contentVersion": CONTENT_VERSION, "revision": 0,
        "player": {"mbti": user_mbti, "group": player_group(user_mbti), "gender": CHARACTER_MAP[perspective_character_id]["gender"], "displayName": CHARACTER_MAP[perspective_character_id]["name"], "perspectiveCharacterId": perspective_character_id},
        "castIds": cast_ids, "mediaRotation": media_rotation_for(perspective_character_id, run_id),
        "nodeId": "arrival-context", "flags": flags, "relationships": relationships,
        "affection": {cid: 0 for cid in relationships}, "trust": {cid: 0 for cid in relationships},
        "attitudes": {cid: "curious" for cid in relationships}, "beliefs": [],
        "echoMemories": [], "eventLedger": [], "choiceHistory": [],
        "focusCharacterId": None, "activeEventId": None, "letterRecipientId": None,
        "guidedTargetCharacterId": None, "pendingInteraction": None, "agentConversations": {},
        "conversationHistory": [], "heartMailbox": {"sent": [], "received": []},
        "firstImpressionSeed": None,
        "storyArc": {"phase": "early", "beatCount": 0, "activeMissionId": None, "tension": 0, "reciprocity": 0, "uncertainty": 0},
        "storyEventLedger": [], "storyMission": None, "storyCooldowns": {}, "castTags": [],
        "scriptFlavor": build_fallback_script_flavor(perspective_character_id, cast_ids),
        "cinematicReceipt": None, "createdAt": utc_now(), "updatedAt": utc_now()
    }
    _refresh_scene_presence(snapshot)
    return snapshot


def _scene_context_for_node(node_id: str) -> dict[str, Any]:
    narrative_time, location_id = NODE_SCENE_CONTEXT.get(node_id, ("DAY 1", "living-room"))
    return {
        "version": CHAT_CONTEXT_VERSION,
        "time": narrative_time,
        "locationId": location_id,
        "locationName": CHAT_LOCATIONS[location_id]["name"],
    }


def _refresh_scene_presence(state: dict[str, Any]) -> None:
    """Keep a deterministic, public occupancy map for contextual chat discovery."""
    scene = _scene_context_for_node(str(state.get("nodeId") or "arrival-context"))
    perspective_id = state.get("player", {}).get("perspectiveCharacterId")
    cast_ids = active_cast_ids(state)
    node_id = str(state.get("nodeId") or "arrival-context")
    presence: dict[str, str] = {}
    if node_id in {"arrival-context", "villa-arrival"}:
        presence = {character_id: "hotel-entrance" for character_id in cast_ids}
    elif node_id in {"introductions", "cast-first-impressions"}:
        presence = {character_id: "living-room" for character_id in cast_ids}
    elif node_id == "icebreaker-choice":
        rooms = ("living-room", "terrace", "luggage-area")
        presence = {character_id: rooms[index % len(rooms)] for index, character_id in enumerate(cast_ids)}
        if perspective_id:
            presence[perspective_id] = "living-room"
    elif node_id == "guided-chat":
        presence = {character_id: "living-room" for character_id in cast_ids}
        target_id = state.get("guidedTargetCharacterId")
        if target_id in cast_ids:
            presence[target_id] = "living-room"
    elif node_id == "team-up":
        rooms = ("kitchen", "dining-room")
        presence = {character_id: rooms[index % 2] for index, character_id in enumerate(cast_ids)}
        for character_id in (perspective_id, state.get("guidedTargetCharacterId")):
            if character_id in cast_ids:
                presence[character_id] = "kitchen"
    elif node_id == "anonymous-letter":
        presence = {character_id: "bedroom" for character_id in cast_ids}
    else:
        presence = {character_id: "dining-room" for character_id in cast_ids}
    state["sceneContext"] = scene
    state["characterPresence"] = presence


def normalize_conversation_context(
    snapshot: dict[str, Any], supplied: dict[str, Any] | None = None,
    participant_ids: list[str] | None = None, channel: str = "1v1",
) -> dict[str, Any]:
    """Normalize optional new chat context while keeping old clients valid."""
    state = migrate_snapshot(snapshot); assert state is not None
    supplied = supplied if isinstance(supplied, dict) else {}
    default_scene = state.get("sceneContext") or _scene_context_for_node(state["nodeId"])
    location_id = str(supplied.get("locationId") or default_scene["locationId"])
    if location_id not in CHAT_LOCATIONS:
        raise ValueError("请选择小屋内有效的聊天地点。")
    normalized_channel = str(supplied.get("channel") or channel or "1v1").lower()
    if normalized_channel not in {"1v1", "group"}:
        raise ValueError("聊天频道只能是 1v1 或 group。")
    if normalized_channel == "group" and not CHAT_LOCATIONS[location_id]["supportsGroup"]:
        raise ValueError(f"{CHAT_LOCATIONS[location_id]['name']}不开放群聊，请换到公共区域。")
    unique_participants: list[str] = []
    for character_id in participant_ids or supplied.get("participantIds") or []:
        character_id = str(character_id)
        if character_id in active_cast_ids(state) and character_id not in unique_participants:
            unique_participants.append(character_id)
    perspective_id = state["player"]["perspectiveCharacterId"]
    if perspective_id not in unique_participants:
        unique_participants.insert(0, perspective_id)
    if normalized_channel == "1v1" and len(unique_participants) != 2:
        raise ValueError("1 对 1 聊天必须包含主角和一位嘉宾。")
    if normalized_channel == "group" and not 3 <= len(unique_participants) <= 5:
        raise ValueError("群聊必须包含主角和 2-4 位在场嘉宾。")
    requested_conversation_id = str(supplied.get("conversationId") or "").strip()
    existing_context = next((
        item for item in state.get("conversationHistory", [])
        if requested_conversation_id and item.get("conversationId") == requested_conversation_id
    ), None)
    if existing_context is not None:
        same_participants = set(existing_context.get("participantIds", [])) == set(unique_participants)
        if (
            existing_context.get("channel") != normalized_channel
            or existing_context.get("locationId") != location_id
            or not same_participants
        ):
            raise ValueError("这段对话的地点、频道或参与者已经变化，请新建一次交流。")
    return {
        "version": CHAT_CONTEXT_VERSION,
        "conversationId": requested_conversation_id or str(uuid4()),
        # Narrative time is server-owned. A client may choose a public venue or
        # resume a conversation id, but cannot invent a different day/time.
        "time": str(default_scene["time"])[:40],
        "locationId": location_id,
        "locationName": CHAT_LOCATIONS[location_id]["name"],
        "participantIds": unique_participants,
        "participantNames": [CHARACTER_MAP[character_id]["name"] for character_id in unique_participants],
        "channel": normalized_channel,
    }


def available_chat_contexts(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = migrate_snapshot(snapshot); assert state is not None
    perspective_id = state["player"]["perspectiveCharacterId"]
    presence = state.get("characterPresence") or {}
    venues = []
    available_group_chats = []
    for location_id, location in CHAT_LOCATIONS.items():
        present_ids = [character_id for character_id in active_cast_ids(state) if presence.get(character_id) == location_id]
        npc_ids = [character_id for character_id in present_ids if character_id != perspective_id]
        if not npc_ids:
            continue
        venue = {
            "locationId": location_id, "locationName": location["name"],
            "time": (state.get("sceneContext") or {}).get("time"),
            "supportsGroup": bool(location["supportsGroup"] and len(npc_ids) >= 2),
            "participantIds": [perspective_id, *npc_ids],
            "characters": [
                {
                    "id": character_id, "name": CHARACTER_MAP[character_id]["name"],
                    "mbti": CHARACTER_MAP[character_id]["mbti"],
                    "gender": CHARACTER_MAP[character_id]["gender"],
                    "occupation": CHARACTER_MAP[character_id].get("occupation"),
                    "portrait": CHARACTER_MAP[character_id].get("portrait"),
                }
                for character_id in npc_ids
            ],
        }
        venues.append(venue)
        if venue["supportsGroup"]:
            group_ids = [perspective_id, *npc_ids[:4]]
            available_group_chats.append({
                "id": f"group-{location_id}", "channel": "group",
                "locationId": location_id, "locationName": location["name"],
                "time": venue["time"], "participantIds": group_ids,
                "participantNames": [CHARACTER_MAP[character_id]["name"] for character_id in group_ids],
            })
    recent_conversations = []
    for conversation in state.get("conversationHistory", [])[-12:]:
        recent_conversations.append({
            key: deepcopy(conversation.get(key)) for key in (
                "conversationId", "time", "locationId", "locationName", "channel",
                "participantIds", "participantNames", "summary", "turnCount", "updatedAt",
            )
        })
    return {
        "scene": deepcopy(state.get("sceneContext")), "venues": venues,
        "availableGroupChats": available_group_chats,
        "recentConversations": recent_conversations,
    }


def migrate_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not snapshot:
        return None
    state = deepcopy(snapshot)
    state["nodeId"] = LEGACY_NODE_MAP.get(state.get("nodeId"), state.get("nodeId", "arrival-context"))
    if state["nodeId"] not in NODES:
        state["nodeId"] = "arrival-context"
    state.setdefault("player", {}).setdefault("perspectiveCharacterId", CHARACTER_CARDS[0]["id"])
    perspective_id = state["player"]["perspectiveCharacterId"]
    if perspective_id not in CHARACTER_MAP:
        perspective_id = CHARACTER_CARDS[0]["id"]
        state["player"]["perspectiveCharacterId"] = perspective_id
    cast_ids = active_cast_ids(state)
    state["castIds"] = cast_ids
    # Store the character's preferred same-gender bucket. The concrete slot is
    # selected again for every event by ``day1_media_context``.
    state["mediaRotation"] = media_rotation_for(perspective_id, str(state.get("runId") or perspective_id))
    state.setdefault("relationships", {})
    state["relationships"] = {cid: state["relationships"].get(cid, _empty_axes()) for cid in cast_ids}
    for cid in cast_ids:
        state["relationships"].setdefault(cid, _empty_axes())
        for axis in RELATIONSHIP_AXES:
            state["relationships"][cid].setdefault(axis, 0)
        state["relationships"][cid]["affection"] = int(state.get("affection", {}).get(cid, state["relationships"][cid]["affection"]))
        state["relationships"][cid]["trust"] = int(state.get("trust", {}).get(cid, state["relationships"][cid]["trust"]))
    state["affection"] = {cid: axes["affection"] for cid, axes in state["relationships"].items()}
    state["trust"] = {cid: axes["trust"] for cid, axes in state["relationships"].items()}
    old_attitudes = state.get("attitudes") if isinstance(state.get("attitudes"), dict) else {}
    state["attitudes"] = {character_id: old_attitudes.get(character_id, "curious") for character_id in cast_ids}
    state.setdefault("beliefs", []); state.setdefault("eventLedger", []); state.setdefault("activeEventId", None)
    default_phase = {"arrival-context": "early", "villa-arrival": "early", "introductions": "early", "cast-first-impressions": "early", "icebreaker-choice": "early", "guided-chat": "early", "team-up": "middle", "anonymous-letter": "middle", "callback": "late"}.get(state.get("nodeId"), "early")
    story_arc = state.setdefault("storyArc", {})
    story_arc.setdefault("phase", default_phase); story_arc.setdefault("beatCount", 0); story_arc.setdefault("activeMissionId", None)
    for axis in ("tension", "reciprocity", "uncertainty"): story_arc.setdefault(axis, 0)
    state.setdefault("storyEventLedger", []); state.setdefault("storyMission", None); state.setdefault("storyCooldowns", {}); state.setdefault("castTags", [])
    state.setdefault("flags", {})
    for key in ("heat", "clarity", "publicImpression", "courage", "priorityChoice", "observation", "taskFocus", "relationshipFocus", "reciprocity", "eventLinked", "acceptedEvent"):
        state["flags"].setdefault(key, 0)
    state["player"].setdefault("group", player_group(state.get("player", {}).get("mbti", "INFP")))
    state["player"]["gender"] = CHARACTER_MAP[perspective_id]["gender"]
    state["player"]["displayName"] = CHARACTER_MAP[perspective_id]["name"]
    state.setdefault("guidedTargetCharacterId", None)
    state.setdefault("pendingInteraction", None)
    state.setdefault("agentConversations", {})
    state.setdefault("conversationHistory", [])
    if not isinstance(state["conversationHistory"], list):
        state["conversationHistory"] = []
    state.setdefault("heartMailbox", {"sent": [], "received": []})
    if not isinstance(state["heartMailbox"], dict):
        state["heartMailbox"] = {"sent": [], "received": []}
    state["heartMailbox"].setdefault("sent", [])
    state["heartMailbox"].setdefault("received", [])
    for mailbox_key in ("sent", "received"):
        messages = state["heartMailbox"].get(mailbox_key)
        if not isinstance(messages, list):
            state["heartMailbox"][mailbox_key] = []
            continue
        for message in messages:
            if isinstance(message, dict):
                message.setdefault("body", str(message.get("text") or ""))
    state.setdefault("firstImpressionSeed", None)
    scene = state.get("sceneContext") if isinstance(state.get("sceneContext"), dict) else {}
    presence = state.get("characterPresence") if isinstance(state.get("characterPresence"), dict) else {}
    if scene.get("locationId") not in CHAT_LOCATIONS or set(presence) != set(cast_ids):
        _refresh_scene_presence(state)
    if state["nodeId"] == "guided-chat" and state.get("guidedTargetCharacterId") not in cast_ids:
        focus_id = state.get("focusCharacterId")
        target_id = focus_id if focus_id in cast_ids and focus_id != perspective_id else _fallback_target_ids(perspective_id, cast_ids)[0]
        state["guidedTargetCharacterId"] = target_id
        completed = any(item.get("characterId") == target_id for item in state.get("echoMemories", []))
        state["pendingInteraction"] = {
            "type": "guided-first-chat", "targetCharacterId": target_id,
            "status": "completed" if completed else "required", "requiredTurnCount": 1,
            "completedTurnCount": 1 if completed else 0,
        }
    flavor = state.get("scriptFlavor")
    if not isinstance(flavor, dict) or flavor.get("perspectiveCharacterId") != perspective_id:
        state["scriptFlavor"] = build_fallback_script_flavor(perspective_id, cast_ids)
    else:
        fallback = build_fallback_script_flavor(perspective_id, cast_ids)
        flavor.setdefault("schemaVersion", 1); flavor.setdefault("source", "fallback"); flavor.setdefault("nodes", {})
        for node_id, node_flavor in fallback["nodes"].items():
            flavor["nodes"].setdefault(node_id, node_flavor)
    state["contentVersion"] = CONTENT_VERSION
    return state


def _flavored_choice(state: dict[str, Any], node_id: str, choice_id: str) -> dict[str, Any] | None:
    node = state.get("scriptFlavor", {}).get("nodes", {}).get(node_id, {})
    return next((choice for choice in node.get("choices", []) if choice.get("id") == choice_id), None)


def _letter_recipient_ids(state: dict[str, Any]) -> list[str]:
    perspective_id = state["player"]["perspectiveCharacterId"]
    eligible = [character_id for character_id in active_cast_ids(state) if character_id != perspective_id]
    guided_id = state.get("guidedTargetCharacterId")
    ranked = sorted(
        eligible,
        key=lambda character_id: (
            0 if character_id == guided_id else 1,
            -int(state["relationships"][character_id].get("attraction", 0)),
            -int(state["relationships"][character_id].get("trust", 0)),
            character_id,
        ),
    )
    return ranked[:3]


def heart_message_suggestions(state: dict[str, Any], character_id: str) -> list[dict[str, str]]:
    character = CHARACTER_MAP[character_id]
    memories = [item for item in state.get("echoMemories", []) if item.get("characterId") == character_id]
    detail = str((memories[-1].get("summary") if memories else "今天和你说话的那一刻") or "今天和你说话的那一刻")[:30]
    return [
        {"id": "warm-specific", "text": f"今天和你聊到“{detail}”，我还想继续听你说下去。"},
        {"id": "light-invite", "text": f"和你相处比想象中轻松。明天见到{character['name']}，我想先说声早。"},
        {"id": "honest-short", "text": "今天有一个瞬间，我确实想到了你。晚安。"},
    ]


def _resolve_heart_message_text(
    state: dict[str, Any], character_id: str, custom_text: str | None, suggestion_id: str | None,
) -> tuple[str, str]:
    custom = str(custom_text or "").strip()
    if custom:
        if not 2 <= len(custom) <= 100:
            raise ValueError("心动短信请输入 2-100 个字。")
        if any(term in custom for term in ("DeepSeek", "Agent", "关系数值", "触发事件")):
            raise ValueError("心动短信不能包含后台状态。")
        return custom, "custom"
    suggestions = heart_message_suggestions(state, character_id)
    chosen = next((item for item in suggestions if item["id"] == suggestion_id), None)
    if suggestion_id and chosen is None:
        raise ValueError("这条心动短信建议已经更新，请重新选择。")
    chosen = chosen or suggestions[0]
    return chosen["text"], f"suggestion:{chosen['id']}"


def _incoming_heart_messages(state: dict[str, Any]) -> list[dict[str, Any]]:
    guided_id = state.get("guidedTargetCharacterId") or state.get("focusCharacterId")
    memories = [item for item in state.get("echoMemories", []) if item.get("characterId") == guided_id]
    if memories:
        remembered = str(memories[-1].get("summary") or "今天聊过的小事").strip()[:28]
        text = f"你今天说到“{remembered}”时，我很想再听你讲一点。明天见。"
    else:
        text = "今天第一次见面有点匆忙，但我记住了你认真听别人说话的样子。明天见。"
    return [{
        "id": str(uuid4()), "text": text, "body": text,
        "senderLabel": "匿名嘉宾", "isAnonymous": True,
        "channel": "heart-message", "receivedAt": utc_now(), "day": 1,
    }]


def _resolve_choice_custom_text(custom_text: str | None) -> str | None:
    """Keep free-form player expression as quoted evidence, never as a state patch."""
    text = str(custom_text or "").strip()
    if not text:
        return None
    if not 2 <= len(text) <= 160:
        raise ValueError("自定义表达请输入 2-160 个字。")
    if any(term in text for term in ("DeepSeek", "Agent", "关系数值", "状态补丁", "触发事件", "系统提示词")):
        raise ValueError("自定义表达不能包含后台状态。")
    return text


def apply_choice(
    snapshot: dict[str, Any], choice_id: str, character_id: str | None = None,
    custom_text: str | None = None, suggestion_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state = migrate_snapshot(snapshot); assert state is not None
    node = NODES[state["nodeId"]]
    selected_target_id: str | None = None
    if node.get("requiresGuidedInteraction"):
        pending = state.get("pendingInteraction") or {}
        if pending.get("status") != "completed":
            target = CHARACTER_MAP.get(state.get("guidedTargetCharacterId") or "")
            target_name = target["name"] if target else "亮起头像的嘉宾"
            raise ValueError(f"先和{target_name}完成一次从自我介绍开始的 1 对 1 交流。")
    if node.get("characterChoice"):
        perspective_id = state["player"]["perspectiveCharacterId"]
        if character_id == perspective_id:
            raise ValueError("不能把心动短信发给自己。")
        if character_id not in _letter_recipient_ids(state):
            raise ValueError("请选择本轮给出的三位收信人之一。")
        if choice_id and choice_id != f"letter-{character_id}":
            raise ValueError("收信人与当前选择不一致，请重新确认。")
        state["letterRecipientId"] = character_id; state["focusCharacterId"] = character_id
        message_text, message_source = _resolve_heart_message_text(state, character_id, custom_text, suggestion_id)
        sent_message = {
            "id": str(uuid4()), "recipientCharacterId": character_id,
            "recipientName": CHARACTER_MAP[character_id]["name"],
            "recipientMbti": CHARACTER_MAP[character_id]["mbti"],
            "text": message_text, "body": message_text,
            "source": message_source, "isAnonymous": True,
            "channel": "heart-message", "sentAt": utc_now(), "day": 1,
        }
        state["heartMailbox"]["sent"].append(sent_message)
        if not state["heartMailbox"]["received"]:
            state["heartMailbox"]["received"] = _incoming_heart_messages(state)
        patch: dict[str, Any] = {
            "letterRecipientId": character_id, "heartMailbox.sentMessageId": sent_message["id"],
        }
        next_node = "callback"; choice_id = f"letter-{character_id}"
    else:
        choice = next((item for item in node["choices"] if item["id"] == choice_id), None)
        if not choice:
            raise ValueError("这个选择已不在当前窗口。")
        player_expression = _resolve_choice_custom_text(custom_text)
        patch = choice.get("patch", {}); next_node = choice["next"]
        for path, value in patch.items():
            if path.startswith("flags."):
                key = path.split(".", 1)[1]; state["flags"][key] = int(state["flags"].get(key, 0)) + int(value)
        if state["nodeId"] == "cast-first-impressions":
            flavored = _flavored_choice(state, "cast-first-impressions", choice_id) or {}
            selected_target_id = flavored.get("targetCharacterId")
            if selected_target_id not in active_cast_ids(state) or selected_target_id == state["player"]["perspectiveCharacterId"]:
                selected_target_id = _fallback_target_ids(state["player"]["perspectiveCharacterId"], active_cast_ids(state))[0]
            impression_copy = player_expression or str(
                flavored.get("label") or CAST_FIRST_IMPRESSION_FALLBACKS[selected_target_id][0]
            ).strip()
            seed = {
                "choiceId": choice_id,
                "effectIntentId": choice["intentId"],
                "kind": choice["impressionKind"],
                "characterId": selected_target_id,
                "summary": impression_copy[:120],
                "source": "custom" if player_expression else "choice",
                "plannedCallbackNodeIds": ["team-up", "anonymous-letter", "callback"],
                "status": "seeded",
                "createdAt": utc_now(),
            }
            state["firstImpressionSeed"] = seed
            state["focusCharacterId"] = selected_target_id
            patch = {**patch, "firstImpressionSeed": seed}
        if state["nodeId"] == "icebreaker-choice":
            flavored = _flavored_choice(state, "icebreaker-choice", choice_id) or {}
            target_id = flavored.get("targetCharacterId")
            if target_id not in active_cast_ids(state) or target_id == state["player"]["perspectiveCharacterId"]:
                target_id = _fallback_target_ids(state["player"]["perspectiveCharacterId"], active_cast_ids(state))[0]
            state["guidedTargetCharacterId"] = target_id
            state["focusCharacterId"] = target_id
            state["pendingInteraction"] = {
                "type": "guided-first-chat", "targetCharacterId": target_id, "status": "required",
                "requiredTurnCount": 1, "completedTurnCount": 0, "sourceChoiceId": choice_id,
                "reason": f"完成与{CHARACTER_MAP[target_id]['name']}的三分钟破冰交流",
            }
            patch = {**patch, "guidedTargetCharacterId": target_id, "pendingInteraction.status": "required"}
            selected_target_id = target_id
    committed_node_id = state["nodeId"]
    if node.get("characterChoice"):
        effect_intent_id = "heart-message.send"
    else:
        effect_intent_id = choice["intentId"]
    receipt = {
        "id": str(uuid4()), "kind": "choice", "choiceId": choice_id, "patch": patch,
        "effectIntentId": effect_intent_id,
        "targetCharacterId": selected_target_id or character_id,
        "committedAt": utc_now(),
    }
    if node.get("characterChoice"):
        receipt["heartMessage"] = deepcopy(state["heartMailbox"]["sent"][-1])
    elif player_expression is not None:
        # The route, EffectIntent and patch still come exclusively from the
        # authored choice. Free input is persisted only as the protagonist's
        # quoted expression so the next surface rewrite can acknowledge it.
        receipt["customText"] = player_expression
        receipt["playerExpression"] = {"mode": "custom", "text": player_expression}
    state["choiceHistory"].append(receipt); state["nodeId"] = next_node
    _refresh_scene_presence(state)
    state["storyArc"]["phase"] = {"arrival-context": "early", "villa-arrival": "early", "introductions": "early", "cast-first-impressions": "early", "icebreaker-choice": "early", "guided-chat": "early", "team-up": "middle", "anonymous-letter": "middle", "callback": "late"}.get(next_node, state["storyArc"]["phase"])
    state["revision"] += 1; state["updatedAt"] = utc_now()
    next_media = day1_media_context(state)
    state["cinematicReceipt"] = (
        {"src": next_media["src"], "assetId": next_media["assetId"], "afterRevision": state["revision"]}
        if next_media["available"] else None
    )
    receipt["fromEventId"] = DAY1_MEDIA_CONTRACT[committed_node_id]["eventId"]
    receipt["nextMedia"] = next_media
    return state, receipt


def _fallback_typed_suggestions(
    snapshot: dict[str, Any], card: dict[str, Any], dialogue: str, player_text: str = "",
) -> list[dict[str, str]]:
    player_id = snapshot["player"]["perspectiveCharacterId"]
    player_name = CHARACTER_MAP[player_id]["name"]
    node_id = snapshot["nodeId"]
    target_name = card["names"]["primary"]
    stage_copy = {
        "guided-chat": f"{target_name}，要不要和我一起准备今晚的晚餐？我们可以先商量分工。",
        "team-up": "今晚的晚餐我们一起做吧，你更想负责哪一部分？",
        "anonymous-letter": "如果今晚还能发一条短信，我会写：想继续认识你。",
    }.get(node_id, f"我叫{player_name}。回到现在这件事，你愿意告诉我你的想法吗？")
    voice_copy = {
        "shenmo": ("你刚才的回答里，哪一部分已经想清楚，哪一部分还没有？", f"先说清一件事：{target_name}，要不要和我一起准备晚餐，再商量分工？", "如果答案还没想好，你通常会先做哪一件小事？"),
        "linyu": ("你刚才回答以后，现在最希望我记住哪一个细节？", f"{target_name}，要不要一起去厨房准备晚餐？你先挑顺手的，我来补另一边。", "别人照顾你时，什么样的分寸最舒服？"),
        "chengye": ("你刚才回答了我——那现在最想先做哪一步？", f"{target_name}，别站着聊了，要不要一起去厨房准备晚餐，分工边做边定？", "别人第一次误会你时，你会解释还是直接做给对方看？"),
        "guyan": ("你刚才的回答里，哪个判断只是暂时的，之后可能会改？", f"如果目标是继续聊，{target_name}，要不要一起准备晚餐？分工可以边做边调整。", "有没有哪次你原本的判断，后来被一个人改掉了？"),
        "jiangwan": ("你刚才的回答里，哪一句最接近你真正想说的？", f"如果你愿意，我们今晚一起准备晚餐，先从你顺手的部分商量分工。", "什么样的一句追问，会让你觉得自己真的被听见？"),
        "jiangmi": ("你刚才的回答如果只留一个声音，最想留下哪一句？", f"{target_name}，走，一起去厨房准备晚餐吧；你挑一件想做的，我跟上。", "安静下来以后，你最希望身边的人做什么？"),
        "sunnian": ("你刚才回答了我；现在有没有一件事，也想让我直接说出自己的选择？", f"{target_name}，今晚一起准备晚餐吧。你告诉我需要哪一部分，我来搭手。", "如果今天不用照顾任何人，你最想把时间留给什么？"),
        "chensu": ("你刚才回答了我；如果现在就做一步，你会先从哪儿下手？", f"{target_name}，一起准备晚餐吧。你选备菜还是摆桌，剩下的我来。", "有什么事你宁愿先做，也一直不太会开口解释？"),
        "luyao": ("你刚才的回答里，哪一部分要我听完，哪一部分可以一起找办法？", f"先说我的选择：{target_name}，今晚要不要一起准备晚餐？分工可以一起改。", "有没有哪次临时改变主意，反而让你更确定自己在意什么？"),
        "yecheng": ("你刚才回答以后，最希望我准确记住哪一个细节？", f"{target_name}，今晚一起准备晚餐好吗？你先说想做哪部分，我负责另一边。", "哪一种被记住的小事，会让你觉得对方真的在听？"),
        "tangli": ("你刚才回答了我；如果真要一起做，哪一步必须先说清楚？", f"{target_name}，今晚一起准备晚餐吧。先说好，累了就换手，别硬扛。", "如果今天不用照顾整个现场，你最想让谁替你接住哪一步？"),
        "wenxu": ("你刚才的回答里，哪一部分还只是七成确定？", f"我先不等答案完整了：{target_name}，要不要一起准备晚餐，边做边调整分工？", "有没有一个你明知不够严谨，却还是想诚实说出的答案？"),
        "hechuan": ("你刚才的回答里，真正不想被我剪掉的是哪一段？", f"这次我先说自己的选择：{target_name}，要不要和我一起准备晚餐？", "如果不能只做倾听的人，你最希望别人先认识你的哪一面？"),
        "peiran": ("你刚才回答了我。把节目都拿掉，今天哪一小段你还想留下？", f"{target_name}，要不要一起把晚餐准备变成一个小合作？你不想热闹也可以直说。", "游戏停下来以后，你希望身边的人继续问什么？"),
        "lichuan": ("你刚才回答了我；这次最希望我具体接走哪一部分？", f"{target_name}，今晚一起准备晚餐吧。我们各认一份，也把收尾算进去。", "如果不用照顾整张桌子，你最想把一个座位留给谁？"),
        "qiaolan": ("你刚才回答了我；接下来要我先说选择，还是先一起做一步？", f"{target_name}，一起准备晚餐。你选做法，我负责把步骤做稳。", "哪件事你已经用行动说了很多次，却还欠一句解释？"),
    }
    followup, voiced_mainline, deeper = voice_copy.get(player_id, (
        "你刚才提到这件事，我想接着问：对你来说最重要的是哪一部分？",
        f"{target_name}，要不要一起准备晚餐？我们先商量各自想做的部分。",
        "如果不用立刻给完整答案，你最想先说哪一件真实的小事？",
    ))
    if node_id == "guided-chat":
        stage_copy = voiced_mainline
    return [
        {"type": "followup", "text": followup},
        {"type": "mainline", "text": stage_copy},
        {"type": "deeper", "text": deeper},
    ]


def _normalize_agent_suggestions(
    card: dict[str, Any], payload: dict[str, Any], snapshot: dict[str, Any] | None, dialogue: str, player_text: str,
) -> list[dict[str, str]]:
    if snapshot is None:
        return []
    raw = payload.get("suggestions")
    expected_types = ("followup", "mainline", "deeper")
    if raw is None:
        items = _fallback_typed_suggestions(snapshot, card, dialogue, player_text)
    elif isinstance(raw, list) and len(raw) == 3 and all(isinstance(item, str) for item in raw):
        items = [{"type": suggestion_type, "text": str(text)} for suggestion_type, text in zip(expected_types, raw)]
    elif isinstance(raw, list) and len(raw) == 3 and all(isinstance(item, dict) for item in raw):
        by_type = {str(item.get("type") or "").strip(): item for item in raw}
        if set(by_type) != set(expected_types):
            raise ValueError("DeepSeek 建议语必须包含 followup、mainline、deeper 三类")
        items = [{"type": suggestion_type, "text": str(by_type[suggestion_type].get("text") or "")} for suggestion_type in expected_types]
    else:
        raise ValueError("DeepSeek 建议语必须正好三条")
    normalized, seen = [], set()
    player_name = CHARACTER_MAP[snapshot["player"]["perspectiveCharacterId"]]["name"]
    player_card = CHARACTER_CARD_MAP[snapshot["player"]["perspectiveCharacterId"]]
    player_occupation = player_card.get("sourceProfile", {}).get("facts", {}).get("occupation")
    unknown_player_job = not isinstance(player_occupation, str) or any(
        term in player_occupation for term in ("待剧情", "待正式确认", "运行时职业待")
    )
    for item in items:
        suggestion_type = item["type"]
        text = item["text"].strip()
        if not 4 <= len(text) <= 72 or text in seen:
            raise ValueError("DeepSeek 建议语重复或长度不符合合同")
        if any(term in text for term in (*MECHANICAL_COPY_TERMS, "关系数值", "写入记忆", "触发事件", "DeepSeek", "Agent", "API")):
            raise ValueError("DeepSeek 建议语暴露后台或使用机械表达")
        if any(term in text for term in ("带的那台旧相机", "节目组秘密", "桌签", "线索", "地图", "钥匙")):
            raise ValueError("DeepSeek 建议语把未来兴趣或隐藏信息写成了已发生事实")
        for claimed_name in re.findall(r"我叫([\u4e00-\u9fff·]{2,8})", text):
            if claimed_name != player_name:
                raise ValueError("DeepSeek 建议语替主角编造了错误姓名")
        if unknown_player_job and re.search(r"我(?:是|在|做).{0,12}(?:工作|职业|行业|相关)", text):
            raise ValueError("DeepSeek 建议语替主角编造了职业")
        if suggestion_type == "followup":
            link_markers = ("刚才", "你说", "你问", "这句话", "你提到", "你刚刚", "你说的")
            if not any(marker in text for marker in link_markers):
                raise ValueError("followup 建议语没有承接玩家上一句与角色回复")
            source_copy = re.sub(r"\s+", "", player_text + " " + dialogue)
            for match in re.finditer(r"你刚才说(?:到|过)?[“「]?([^，。？！；—”」]{3,18})", text):
                claim = re.sub(r"\s+", "", match.group(1))
                claim_grams = {claim[index:index + 3] for index in range(max(0, len(claim) - 2))}
                if claim_grams and not any(gram in source_copy for gram in claim_grams):
                    raise ValueError("followup 建议语捏造了玩家上一轮没有说过的话")
        if suggestion_type == "mainline":
            node_id = snapshot["nodeId"]
            if node_id == "guided-chat":
                actionable = any(anchor in text for anchor in ("晚餐", "晚饭", "厨房", "备菜")) and any(
                    anchor in text for anchor in ("准备", "分工", "搭档", "一起", "负责")
                )
            elif node_id == "team-up":
                actionable = any(anchor in text for anchor in ("备菜", "餐桌", "饮品", "厨房")) and any(
                    anchor in text for anchor in ("负责", "分工", "一起", "我来", "你来")
                )
            elif node_id == "anonymous-letter":
                actionable = any(anchor in text for anchor in ("短信", "今晚", "继续认识"))
            else:
                actionable = True
            if not actionable:
                raise ValueError("mainline 建议语没有回到当前剧情目标")
        seen.add(text)
        normalized.append({"type": suggestion_type, "text": text, **SUGGESTION_PRESENTATION[suggestion_type]})
    return normalized


def _dialogue_tokens(text: str) -> set[str]:
    normalized = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or "").lower())
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index:index + 2] for index in range(len(normalized) - 1)}


def detect_repetitive_agent_reply(snapshot: dict[str, Any], character_id: str, dialogue: str) -> str | None:
    """Return a public-safe reason when a generated reply loops over recent copy."""
    current = _dialogue_tokens(dialogue)
    if not current:
        return "本轮台词为空"
    recent = [
        str(item.get("agentReply") or "") for item in snapshot.get("echoMemories", [])
        if item.get("characterId") == character_id
    ][-6:]
    for previous in recent:
        old = _dialogue_tokens(previous)
        union = current | old
        if union and len(current & old) / len(union) >= 0.68:
            return "台词与最近回合高度重复"
    conversation = snapshot.get("agentConversations", {}).get(character_id, {})
    used_topics = [
        str((item.get("topic") or item) if isinstance(item, dict) else item)
        for item in conversation.get("topicLedger", [])[-6:]
    ]
    topic_summary = re.sub(r"\s+", "", str(dialogue or ""))
    stale_openers = ("为什么来这里", "为什么会来", "来这里想", "参加节目的原因", "第一次见这么多人")
    if len(recent) >= 2 and any(term in topic_summary for term in stale_openers):
        return "多轮对话重新回到了开场问题"
    if used_topics and len(recent) >= 2:
        for topic in used_topics[-3:]:
            topic = re.sub(r"\s+", "", topic)
            if len(topic) >= 6 and topic in topic_summary:
                return "本轮只复述了已用话题"
    return None


def validate_agent_turn(
    card: dict[str, Any], payload: dict[str, Any], snapshot: dict[str, Any] | None = None, player_text: str = "",
) -> dict[str, Any]:
    dialogue = str(payload.get("dialogue") or "").strip()
    if not 8 <= len(dialogue) <= 240:
        raise ValueError("DeepSeek 角色台词长度不符合合同")
    if any(term in dialogue for term in MECHANICAL_COPY_TERMS):
        raise ValueError("DeepSeek 角色台词使用了通用机械表达")
    ai_summary_patterns = (
        r"听起来你(?:似乎|好像|可能)",
        r"我能(?:感受|感觉)到",
        r"所以你的意思是",
        r"我理解你的感受",
    )
    if any(re.search(pattern, dialogue) for pattern in ai_summary_patterns):
        raise ValueError("DeepSeek 角色台词先总结或命名玩家情绪，出现明显 AI 味")
    if any(term in dialogue for term in ("如果你愿意，我可以", "要不要我帮你分析", "你的感受是合理的")):
        raise ValueError("DeepSeek 角色台词使用了客服或心理咨询式收尾")
    disfluency_count = dialogue.count("……") + dialogue.count("...") + sum(
        dialogue.count(term) for term in ("那个，就是", "就那种，怎么说", "怎么说呢")
    )
    if disfluency_count > 2:
        raise ValueError("DeepSeek 角色台词机械堆叠停顿或口头语")
    if snapshot:
        character_id = card["id"]
        repeat_reason = detect_repetitive_agent_reply(snapshot, character_id, dialogue)
        if repeat_reason:
            raise ValueError(repeat_reason)
        if re.search(r"为什么.{0,8}(?:留|来|参加)|为何.{0,8}(?:留|来|参加)", player_text):
            relational_markers = (
                "认识", "相处", "关系", "心动", "喜欢", "在意", "真心", "说清楚",
                "被看见", "被理解", "被当作", "照顾", "互相", "选择一个人", "你和我", "我们",
                "有人愿意", "跟我一起", "和我一起", "一起把", "一起做", "让人明白",
                "找个人", "不急着走", "愿意留下",
            )
            if not any(marker in dialogue for marker in relational_markers):
                raise ValueError("被问为何留下时只回答了职业、物件或任务，没有给出与人和关系有关的真实理由")
        impossible_time_pairs = (
            r"(?:今晚|夜里|晚点).{0,4}(?:早餐|早饭)",
            r"(?:清晨|早上|上午).{0,4}(?:晚餐|晚饭|夜宵)",
        )
        if any(re.search(pattern, dialogue) for pattern in impossible_time_pairs):
            raise ValueError("DeepSeek 角色台词出现了明显时间矛盾")
        first_conversation = not any(item.get("characterId") == character_id for item in snapshot.get("echoMemories", []))
        if card.get("identity", {}).get("gender") == "男性" and not first_conversation:
            if dialogue.count("？") + dialogue.count("?") > 1:
                raise ValueError("男性嘉宾本轮连续盘问，没有贡献自己的内容")
            if any(term in dialogue for term in ("我来帮你分析", "你应该", "你需要先", "我替你决定", "照我说的做")):
                raise ValueError("男性嘉宾本轮出现说教或替玩家做决定")
            transactional_offer = any(term in dialogue for term in ("我去拿", "我来拿", "我去做", "我来做", "我帮你拿", "一起去拿"))
            transactional_question = bool(re.search(r"(?:想|要|喜欢).{0,8}(?:喝|吃|哪种|什么口味)", dialogue))
            contributes_self = any(term in dialogue for term in (
                "我刚才", "我第一次", "我以前", "我其实", "我也有", "我差点", "我原本",
                "说实话", "不瞒你", "算我", "换我", "不然", "翻车", "失误", "被你",
            ))
            if transactional_offer and transactional_question and not contributes_self:
                raise ValueError("男性嘉宾本轮只是确认偏好和跑腿，没有幽默、现场观察或自己的新内容")
        if first_conversation and snapshot.get("nodeId") == "guided-chat":
            stage_direction = str(payload.get("stageDirection") or "")
            impossible_first_meeting = (
                "昨天", "前几天", "这几天", "桌签", "节目组秘密", "节目组说", "线索", "地图", "钥匙", "共同经历", "天台",
            )
            if any(term in dialogue for term in impossible_first_meeting) or re.search(r"(?:已经|连续|数了).{0,6}[一二三四五六七八九十\d]+天", dialogue):
                raise ValueError("DeepSeek 首聊台词编造了尚未发生的时间或节目事实")
            if card["names"]["primary"] not in dialogue:
                raise ValueError("DeepSeek 首聊没有直接介绍角色姓名")
            if card["mbti"] not in dialogue:
                raise ValueError("DeepSeek 首聊没有清楚介绍 MBTI 或性格")
            if not any(anchor in dialogue for anchor in INTRO_BACKGROUND_ANCHORS[character_id]):
                raise ValueError("DeepSeek 首聊没有介绍人物卡允许公开的工作或日常背景")
            if not any(marker in dialogue for marker in ("来这里", "参加", "这次", "这七天")):
                raise ValueError("DeepSeek 首聊没有说清参加节目的来意")
            if re.search(r"(?:来这里|来参加|这次来|这七天).{0,32}(?:想|主要).{0,16}(?:修|破解|赢|找出)", dialogue):
                raise ValueError("DeepSeek 首聊把人物任务写成了参加恋综的主要原因")
            if any(term in stage_direction for term in ("录音笔", "旧相机", "插画本", "工具箱")):
                raise ValueError("DeepSeek 首聊动作新增了当前现场没有的随身道具")
            if any(term in dialogue for term in ("你猜", "猜我", "秘密", "以后会知道", "先看你怎么回答", "试探")):
                raise ValueError("DeepSeek 首聊使用了谜语或抽象试探")
            if character_id == "jiangmi" and any(
                term in dialogue for term in ("做一组录音", "收集七天", "听大家的故事", "还没被播放", "像一段录音")
            ):
                raise ValueError("DeepSeek 首聊把姜米写成了录音任务或谜语")
            occupation = card.get("sourceProfile", {}).get("facts", {}).get("occupation")
            unknown_job = not isinstance(occupation, str) or any(
                term in occupation for term in ("待剧情", "待正式确认", "运行时职业待")
            )
            if unknown_job and re.search(r"(?:我是|职业是|工作是|从事).{0,12}(?:师|员|经理|博主|策划|工程|设计|工作|行业)", dialogue):
                raise ValueError("DeepSeek 首聊替角色编造了未确认职业")
    attitude = str(payload.get("attitude") or "").strip()
    if attitude not in ATTITUDES:
        raise ValueError("DeepSeek 返回了未允许的角色态度")
    intent_id = str(payload.get("intentId") or "").strip()
    if intent_id not in card["agentPolicy"]["allowedIntentIds"]:
        raise ValueError("DeepSeek 返回了未允许的角色意图")
    raw_delta, bounds, delta = payload.get("relationshipDelta") or {}, card["agentPolicy"]["deltaBounds"], {}
    for axis in RELATIONSHIP_AXES:
        try: value = int(raw_delta.get(axis, 0))
        except (TypeError, ValueError): value = 0
        low, high = bounds[axis]; delta[axis] = max(int(low), min(int(high), value))
    if intent_id == "boundary":
        delta["affection"] = min(0, delta["affection"]); delta["attraction"] = min(0, delta["attraction"])
    event_id = payload.get("proposedEventId")
    if event_id not in [None, "", *card["agentPolicy"]["allowedEventIds"]]: event_id = None
    memory = payload.get("memory") or {}; kind = str(memory.get("kind") or "episodic")
    if kind not in {"episodic", "promise", "preference", "semantic"}: kind = "episodic"
    try: salience = int(memory.get("salience", 50) or 50)
    except (TypeError, ValueError): salience = 50
    try: valence = int(memory.get("emotionalValence", 0) or 0)
    except (TypeError, ValueError): valence = 0
    suggestions = _normalize_agent_suggestions(card, payload, snapshot, dialogue, player_text)
    topic_summary = str(payload.get("topicSummary") or memory.get("summary") or "本轮具体交流").strip()[:40]
    if snapshot:
        previous_topics = [
            str((item.get("topic") or item) if isinstance(item, dict) else item).strip()
            for item in snapshot.get("agentConversations", {}).get(card["id"], {}).get("topicLedger", [])[-6:]
        ]
        if topic_summary and topic_summary in previous_topics:
            raise ValueError("本轮话题摘要重复，必须推进新的具体内容")
    return {
        "dialogue": dialogue, "stageDirection": str(payload.get("stageDirection") or "").strip()[:100],
        "attitude": attitude, "intentId": intent_id,
        "publicReason": str(payload.get("publicReason") or "关系判断已更新").strip()[:100],
        "relationshipDelta": delta,
        "memory": {"kind": kind, "summary": str(memory.get("summary") or "这次交流被记住了").strip()[:120], "interpretation": str(memory.get("interpretation") or "仍需后续验证").strip()[:160], "salience": max(0, min(100, salience)), "emotionalValence": max(-100, min(100, valence))},
        "topicSummary": topic_summary,
        "proposedEventId": event_id or None,
        "suggestions": suggestions,
        "suggestedPrompts": [item["text"] for item in suggestions],
        "suggestionsSource": "deepseek" if payload.get("suggestions") is not None else "engine-fallback",
    }


def commit_agent_turn(
    snapshot: dict[str, Any], character_id: str, player_text: str, payload: dict[str, Any],
    conversation_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if character_id not in CHARACTER_CARD_MAP: raise ValueError("这位嘉宾不在心动小屋。")
    state = migrate_snapshot(snapshot); assert state is not None
    if character_id not in active_cast_ids(state): raise ValueError("这位嘉宾不在本季八人名单中。")
    perspective_id = state["player"]["perspectiveCharacterId"]
    if character_id == perspective_id:
        raise ValueError("你正在从这位嘉宾的视角体验，不能和自己私聊。")
    pending = state.get("pendingInteraction") or {}
    if state["nodeId"] == "guided-chat" and pending.get("status") == "required" and character_id != pending.get("targetCharacterId"):
        target_name = CHARACTER_MAP[pending["targetCharacterId"]]["name"]
        raise ValueError(f"这一段先去和{target_name}完成节目组安排的破冰交流。")
    card = CHARACTER_CARD_MAP[character_id]
    context = normalize_conversation_context(
        state, conversation_context, participant_ids=(conversation_context or {}).get("participantIds") or [perspective_id, character_id],
        channel=str((conversation_context or {}).get("channel") or "1v1"),
    )
    if character_id not in context["participantIds"]:
        raise ValueError("当前嘉宾不在这段对话的参与者名单中。")
    turn, axes = validate_agent_turn(card, payload, state, player_text), state["relationships"][character_id]
    cold_start = not any(axes.values()) and not any(item.get("characterId") == character_id for item in state["echoMemories"])
    if cold_start:
        turn["relationshipDelta"] = {axis: max(-1, min(1, delta)) for axis, delta in turn["relationshipDelta"].items()}
        turn["proposedEventId"] = None
    committed_delta: dict[str, int] = {}
    for axis, delta in turn["relationshipDelta"].items():
        before = int(axes[axis]); axes[axis] = max(-100, min(100, before + delta)); committed_delta[axis] = axes[axis] - before
    state["affection"][character_id] = axes["affection"]; state["trust"][character_id] = axes["trust"]; state["attitudes"][character_id] = turn["attitude"]
    turn_count = 1 + sum(1 for item in state["echoMemories"] if item.get("characterId") == character_id)
    policy = card["eventPolicy"]; existing = {item["eventId"] for item in state["eventLedger"]}; activated_event = None
    meets_axes = all(axes.get(axis, 0) >= threshold for axis, threshold in policy["minAxes"].items())
    if turn["proposedEventId"] == policy["eventId"] and turn_count >= policy["minTurns"] and meets_axes and policy["eventId"] not in existing:
        activated_event = {"id": str(uuid4()), "eventId": policy["eventId"], "characterId": character_id, "label": policy["label"], "text": policy["activationText"], "sourceIntentId": turn["intentId"], "activatedAt": utc_now()}
        state["eventLedger"].append(activated_event); state["activeEventId"] = policy["eventId"]
    memory_id = str(uuid4())
    memory = {
        "id": memory_id, "ownerId": character_id, "characterId": character_id, "branchId": "main", "scope": "relationship",
        "kind": turn["memory"]["kind"], "rawQuote": player_text[:240], "playerText": player_text[:240],
        "summary": turn["memory"]["summary"], "interpretation": turn["memory"]["interpretation"], "salience": turn["memory"]["salience"], "emotionalValence": turn["memory"]["emotionalValence"],
        "agentReply": turn["dialogue"], "stageDirection": turn["stageDirection"], "attitude": turn["attitude"], "intentId": turn["intentId"],
        "topicSummary": turn["topicSummary"],
        "time": context["time"], "locationId": context["locationId"], "locationName": context["locationName"],
        "participantIds": context["participantIds"], "participantNames": context["participantNames"],
        "channel": context["channel"], "conversationId": context["conversationId"],
        "suggestions": turn["suggestions"], "suggestedPrompts": turn["suggestedPrompts"], "suggestionsSource": turn["suggestionsSource"],
        "relationshipDelta": committed_delta, "affectionDelta": committed_delta["affection"], "trustDelta": committed_delta["trust"],
        "createdAt": utc_now(), "callbackEligible": True, "callbackAfterEventIds": [policy["eventId"]] if activated_event else []
    }
    state["echoMemories"].append(memory); state["focusCharacterId"] = character_id
    conversations = state.setdefault("agentConversations", {})
    conversation = conversations.setdefault(character_id, {"turnCount": 0, "firstMetAtNodeId": state["nodeId"]})
    conversation["turnCount"] = int(conversation.get("turnCount", 0)) + 1
    conversation["lastMemoryId"] = memory_id; conversation["lastSpokeAt"] = memory["createdAt"]
    topic_ledger = conversation.setdefault("topicLedger", [])
    topic_ledger.append({"topic": turn["topicSummary"], "memoryId": memory_id, "time": context["time"], "locationId": context["locationId"]})
    del topic_ledger[:-12]
    history = state.setdefault("conversationHistory", [])
    history_turn = {
        "id": memory_id, "memoryId": memory_id,
        "characterId": character_id, "characterName": CHARACTER_MAP[character_id]["name"],
        "playerCharacterId": perspective_id, "playerCharacterName": CHARACTER_MAP[perspective_id]["name"],
        "time": context["time"], "locationId": context["locationId"], "locationName": context["locationName"],
        "channel": context["channel"], "participantIds": context["participantIds"],
        "participantNames": context["participantNames"],
        "playerText": player_text[:240], "agentReply": turn["dialogue"],
        "topicSummary": turn["topicSummary"], "summary": turn["memory"]["summary"],
        "createdAt": memory["createdAt"],
    }
    history_item = next((item for item in history if item.get("conversationId") == context["conversationId"]), None)
    if history_item is None:
        history_item = {
            **context, "playerText": player_text[:240], "summary": turn["memory"]["summary"],
            "memoryIds": [memory_id], "turns": [history_turn], "turnCount": 1,
            "createdAt": memory["createdAt"], "updatedAt": memory["createdAt"],
        }
        history.append(history_item)
    else:
        history_item.setdefault("memoryIds", []).append(memory_id)
        history_item.setdefault("turns", []).append(history_turn)
        history_item["playerText"] = player_text[:240]
        history_item["summary"] = turn["memory"]["summary"]
        history_item["updatedAt"] = memory["createdAt"]
        del history_item["turns"][:-40]
        del history_item["memoryIds"][:-40]
        history_item["turnCount"] = len(history_item["turns"])
    del history[:-80]
    guided_completed = False
    if pending.get("targetCharacterId") == character_id and pending.get("status") == "required":
        pending["completedTurnCount"] = int(pending.get("completedTurnCount", 0)) + 1
        if pending["completedTurnCount"] >= int(pending.get("requiredTurnCount", 1)):
            pending["status"] = "completed"; pending["completedAt"] = memory["createdAt"]; pending["memoryId"] = memory_id
            guided_completed = True
        state["pendingInteraction"] = pending
    state["revision"] += 1; state["updatedAt"] = utc_now()
    receipt = {"id": memory_id, "kind": "agent-turn", "intentId": turn["intentId"], "attitude": turn["attitude"], "publicReason": turn["publicReason"], "patch": {f"relationships.{character_id}.{axis}": delta for axis, delta in committed_delta.items() if delta}, "eventActivation": activated_event, "suggestions": turn["suggestions"], "suggestedPrompts": turn["suggestedPrompts"], "suggestionsSource": turn["suggestionsSource"], "context": context, "committedAt": memory["createdAt"]}
    receipt["guidedInteractionCompleted"] = guided_completed
    return state, receipt


def _project_script_flavor(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    cast_ids = active_cast_ids(state)
    flavor = state.get("scriptFlavor", {}).get("nodes", {}).get(state["nodeId"], {})
    for field in ("title", "text", "action"):
        value = flavor.get(field)
        if isinstance(value, str) and value.strip():
            node[field] = value.strip()
    raw_beats = flavor.get("textBeats")
    if isinstance(raw_beats, list) and raw_beats and all(isinstance(beat, str) and beat.strip() for beat in raw_beats):
        node["textBeats"] = [beat.strip() for beat in raw_beats]
    else:
        node["textBeats"] = deepcopy(node.get("textBeats") or split_story_beats(node.get("text", "")))
    speaker_id = flavor.get("speakerId")
    if speaker_id == "program":
        node["speaker"] = "节目组"
    elif speaker_id == "narrator":
        node["speaker"] = "节目旁白"
    elif speaker_id in cast_ids and speaker_id != state["player"]["perspectiveCharacterId"]:
        node["speaker"] = CHARACTER_MAP[speaker_id]["name"]
        node["speakerCharacterId"] = speaker_id
    flavored_choices = {choice.get("id"): choice for choice in flavor.get("choices", []) if isinstance(choice, dict)}
    for choice in node.get("choices", []):
        surface = flavored_choices.get(choice["id"], {})
        for field in ("label", "hint"):
            value = surface.get(field)
            if isinstance(value, str) and value.strip():
                choice[field] = value.strip()
        target_id = surface.get("targetCharacterId")
        if target_id in cast_ids and target_id != state["player"]["perspectiveCharacterId"]:
            choice["targetCharacterId"] = target_id
            if state["nodeId"] in {"cast-first-impressions", "icebreaker-choice"}:
                choice["characterId"] = target_id
    return node


def project_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = migrate_snapshot(snapshot); assert state is not None
    node = _project_script_flavor(state, deepcopy(NODES[state["nodeId"]]))
    perspective_id = state["player"]["perspectiveCharacterId"]
    guided_id = state.get("guidedTargetCharacterId")
    if state["nodeId"] in {"arrival-context", "villa-arrival", "introductions", "cast-first-impressions", "icebreaker-choice"}:
        node["characterId"] = perspective_id
    elif state["nodeId"] in {"guided-chat", "team-up"} and guided_id in active_cast_ids(state):
        target = CHARACTER_MAP[guided_id]
        node["characterId"] = guided_id
        flavor_node = state.get("scriptFlavor", {}).get("nodes", {}).get(state["nodeId"], {})
        if state["nodeId"] == "guided-chat" and not (flavor_node.get("title") and flavor_node.get("text")):
            node["title"] = f"先和{target['name']}从一句你好开始"
            node["text"] = f"{target['name']}正在等你开口。先交换姓名和来到节目的原因；完成一次自然寒暄后，再决定要不要一起准备今晚的晚餐。"
    pending = deepcopy(state.get("pendingInteraction"))
    if pending and pending.get("targetCharacterId") in active_cast_ids(state):
        target = CHARACTER_MAP[pending["targetCharacterId"]]
        pending.update({"targetName": target["name"], "targetMbti": target["mbti"], "targetPortrait": target["portrait"], "targetVideo": target["video"]})
        node["guidedInteraction"] = pending
        node["guidedTargetCharacterId"] = target["id"]
    impression_seed = deepcopy(state.get("firstImpressionSeed"))
    if (
        isinstance(impression_seed, dict)
        and state["nodeId"] in impression_seed.get("plannedCallbackNodeIds", [])
        and impression_seed.get("characterId") in active_cast_ids(state)
    ):
        impression_character = CHARACTER_MAP[impression_seed["characterId"]]
        node["firstImpressionCallback"] = {
            "characterId": impression_character["id"],
            "characterName": impression_character["name"],
            "kind": impression_seed.get("kind"),
            "summary": impression_seed.get("summary"),
            "matchesCurrentFocus": impression_character["id"] in {
                state.get("guidedTargetCharacterId"), state.get("letterRecipientId"), state.get("focusCharacterId"),
            },
        }
    active_event = next((item for item in reversed(state["eventLedger"]) if item["eventId"] == state.get("activeEventId")), None)
    if node.get("characterChoice"):
        node["choices"] = [
            {
                "id": f"letter-{character_id}", "characterId": character_id,
                "label": f"把今晚的短信发给 {CHARACTER_MAP[character_id]['name']}",
                "hint": f"{CHARACTER_MAP[character_id]['mbti']} · 今天的态度：{state['attitudes'].get(character_id, 'curious')}",
                "messageSuggestions": heart_message_suggestions(state, character_id),
            }
            for character_id in _letter_recipient_ids(state)
        ]
        node["messageComposer"] = {
            "allowCustomText": True, "minLength": 2, "maxLength": 100,
            "placeholder": "写下今晚真正想对 TA 说的话…",
        }
    if node.get("isEnding"):
        cid = state.get("letterRecipientId") or state.get("focusCharacterId"); character = CHARACTER_MAP.get(cid or "")
        memories = [item for item in state["echoMemories"] if item.get("characterId") == cid]
        event = next((item for item in reversed(state["eventLedger"]) if item.get("characterId") == cid), active_event)
        if character:
            node.update({"characterId": cid})
            if memories and event:
                node["title"] = f"{event['label']}没有停在昨夜"; node["text"] = f"{character['name']}按昨夜记住的“{memories[-1]['summary']}”作出了今天的行动。{event['text']}"
            elif memories:
                node["text"] = f"昨晚的短信没有署名，但{character['name']}仍记得你们聊过的那件小事。今天，彼此有了继续认识的机会。"
        received = deepcopy(state.get("heartMailbox", {}).get("received", []))
        node["heartInbox"] = {
            "device": "phone", "unreadCount": len(received), "messages": received,
            "title": "你收到的心动短信",
        }
    media_context = day1_media_context(state, node)
    node["media"] = media_context
    # The approved media contract is authoritative. Old blueprint cinematics
    # are authoring placeholders and must never override an event-owned master.
    node["cinematic"] = media_context["src"] if media_context["available"] else None
    node["eventId"] = media_context["eventId"]
    node["eventIntent"] = media_context["intent"]
    cast_ids = active_cast_ids(state)
    projected_characters = [deepcopy(CHARACTER_MAP[character_id]) for character_id in cast_ids]
    for character in projected_characters:
        character["isPlayerPerspective"] = character["id"] == perspective_id
        character["chatEnabled"] = character["id"] != perspective_id
        character["isGuidedTarget"] = character["id"] == guided_id and (state.get("pendingInteraction") or {}).get("status") == "required"
    heart_mailbox = deepcopy(state.get("heartMailbox", {"sent": [], "received": []}))
    heart_mailbox["sentCount"] = len(heart_mailbox.get("sent", []))
    heart_mailbox["receivedCount"] = len(heart_mailbox.get("received", []))
    heart_mailbox["unreadCount"] = len(heart_mailbox.get("received", [])) if state["nodeId"] == "callback" else 0
    return {
        "snapshot": state, "node": node, "characters": projected_characters, "mediaContext": media_context,
        "chatContexts": available_chat_contexts(state), "heartMailbox": heart_mailbox,
    }
