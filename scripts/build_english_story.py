"""Bind editorial English copy to the unchanged authored story and character IDs."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import game_content as g

copy = {
    "节目旁白": "Narrator", "节目组": "Production team", "节目提示": "Show guide",
    "酒店玄关": "Hotel entrance", "客厅": "Living room", "海景露台": "Seaview terrace",
    "行李区": "Luggage area", "开放厨房": "Open kitchen", "餐厅": "Dining room", "卧室": "Bedroom",
    "匿名嘉宾": "Anonymous guest", "你收到的心动短信": "Your heart messages",
    "写下今晚真正想对 TA 说的话…": "Write what you really want to tell them tonight…",
    "今天有一个瞬间，我确实想到了你。晚安。": "There was a moment today when I found myself thinking of you. Good night.",
    "今天第一次见面有点匆忙，但我记住了你认真听别人说话的样子。明天见。": "Our first meeting was a little rushed, but I noticed how carefully you listened. See you tomorrow.",
    "今天和你说话的那一刻": "the moment we talked today", "今天聊过的小事": "that small thing we talked about today",
    "姓名写在卡上；从自我介绍里没说完的一句接着聊": "Their name is on the card. Pick up something they left unfinished in their introduction.",
    "问题容易回答，也能听见对方真实的期待": "An easy question that leaves room for an honest answer.",
    "从眼前能一起完成的小事开口，不必硬找话题": "Start with something you can do together. You don't need a perfect opening line.",
    "大家围着客厅坐下，轮流说出姓名、公开背景和来到这里的原因。现在镜头来到你：不用准备漂亮答案，让陌生人先认识一个真实、具体的你。": "Everyone sits down in the living room and shares their name, background, and reason for coming. Now the camera turns to you. You don't need a polished answer—just give these strangers something real to know about you.",
    "把姓名、公开背景和参加原因自然说清": "Share your name, background, and reason for joining.",
    "简短介绍自己，再留一个每个人都容易回答的问题": "Introduce yourself briefly, then ask an easy question.",
    "交代公开信息，也说出第一眼印象背后的真实期待": "Share your background and what you hope people will see beyond a first impression.",
}

STORY = {
    "arrival-context": {
        "chapter": "DAY 1 · The journey begins", "eyebrow": "Heart Journey / Prologue",
        "title": "Seven days, six nights. Start with hello.",
        "text": "Eight guests will spend seven days and six nights together at an island hotel. You'll share meals, outings, games—and the excitement, hesitation, and misunderstandings that come with getting close. You may learn something about yourself along the way.",
        "action": "Evening light crosses the sea as the camera approaches the island hotel, its windows glowing.",
        "mediaCue": "An island hotel, approaching cars, and eight guests who have yet to meet.",
        "choices": [
            ["Get to know each person properly", "Give people time to show you who they are."],
            ["Start with the small things in shared life", "Meals, errands, and everyday moments can bring you closer."],
            ["Learn something new about myself, too", "Let yourself feel a spark—and change your mind."],
        ],
    },
    "villa-arrival": {
        "chapter": "DAY 1 · Island arrival", "eyebrow": "Heart Hotel / 17:30",
        "title": "Welcome to Heart Journey",
        "text": "Eight guests are here for seven days and six nights. Cooking, trips, games, and time together may spark connections no one expected.",
        "action": "The cars stop outside the hotel. Eight suitcases are unloaded one by one.",
        "mediaCue": "The eight guests arrive at the island hotel, carry their luggage, and meet for the first time.",
        "gameBrief": {
            "name": "Seven days, six nights. Start with hello.",
            "format": "Share daily life and the show's activities. Each evening, you can send a heart message to the person you'd most like to keep getting to know.",
            "winCondition": "There is no leaderboard. At the end of the journey, you can choose someone you'd like to see again—or leave knowing yourself a little better.",
            "strategyPrompt": "You've just entered the hotel. What do you do first?",
            "strategyOptions": ["Help someone with their luggage", "Say hello to everyone in the living room", "Remember everyone's name and where they are"],
        },
        "choices": [
            ["Take a suitcase from someone beside me", "A small gesture can open the conversation."],
            ["Go into the living room and say hello", "Let everyone put a name to your face."],
            ["Hang back and notice what everyone is doing", "Bring a few real observations into the icebreaker."],
        ],
    },
    "introductions": {
        "chapter": "DAY 1 · First meetings", "eyebrow": "Hotel living room / 18:05",
        "title": "Eight names, said out loud for the first time",
        "text": "Everyone sits down in the living room. The production team asks each guest who they are, what they do, and why they chose to spend seven days with strangers. Now it's your turn.",
        "action": "The camera moves across the seated guests, then stops at your seat.",
        "mediaCue": "Eight guests sit together in the island villa and introduce themselves in turn.",
        "choices": [
            ["Introduce my name, work, and reason for joining", "Give people something clear they can ask about."],
            ["Introduce myself, then ask everyone a question", "Open up an easy exchange."],
            ["Admit I'm nervous and share something honest", "Let them see a real person, without trying to be perfect."],
        ],
    },
    "cast-first-impressions": {
        "chapter": "DAY 1 · First impressions", "eyebrow": "Hotel living room / 18:18",
        "title": "The last name is spoken. The room grows quiet.",
        "text": "You stay seated while the other seven guests introduce themselves. Some speak plainly about work and why they came; some admit they're nervous on camera; others turn a question back to the room. By the last introduction, one person has caught your attention. Dinner and tonight's messages may change that first impression.",
        "textBeats": ["You stay seated while the other seven guests introduce themselves.", "Some speak plainly, some admit they're nervous, and others ask the room a question.", "By the last introduction, one person has caught your attention.", "Dinner and tonight's messages may change that first impression."],
        "action": "The camera catches each guest's expression before returning to your hands resting on your knees.",
        "mediaCue": "The lead hears the other seven guests and starts to form a first impression.",
        "choices": [
            ["Remember the person who listened to every introduction", "You'll need another conversation to know what their quiet means."],
            ["Notice the person who kept helping others find their words", "Someone who looks after the room may want to be asked about themselves."],
            ["Remember the person whose introduction surprised me", "Keep that contrast in mind and see what they do next."],
        ],
    },
    "icebreaker-choice": {
        "chapter": "DAY 1 · Break the ice", "eyebrow": "Hotel common area / 18:25",
        "title": "Three cards. One guest. Three minutes.",
        "text": "Three cards on the table name the living room, terrace, and luggage area. Each points to a guest you haven't spoken to alone. Pick one and find that person. Ask about their introduction or something happening nearby. After three minutes, return and share one small thing they actually told you. If they confirm or add to it, you've completed the icebreaker.",
        "textBeats": ["Three cards name the living room, terrace, and luggage area. Each points to one guest.", "Pick a card, find that person, and talk for three minutes.", "Ask about their introduction or something happening nearby.", "Return with one small thing they told you. Their confirmation completes the icebreaker."],
        "action": "Three cards with locations and guest names are turned face up in the middle of the table.",
        "mediaCue": "Guests pick a card in the living room and head to separate areas for an icebreaker.",
        "gameBrief": {
            "name": "Three minutes. Remember one small thing.",
            "format": "Each card names a place and a guest. Go there and talk alone for three minutes. The cards aren't matchmaking results or a hidden puzzle.",
            "winCondition": "Back in the living room, share one real thing the guest told you. If they confirm it or add a detail, you were listening.",
            "strategyPrompt": "Look at the guest and opening on each card. Pick the conversation you actually want to have.",
            "strategyOptions": ["Ask about something left unfinished in their introduction", "Start with what they're doing right now", "Exchange your real reasons for joining the show"],
        },
        "choices": [
            ["Help a guest organize what's beside them", "Get to know each other while doing something small."],
            ["Walk up to a guest and exchange names", "A simple hello is enough to start."],
            ["Ask a guest what they were just doing", "Start with something you actually noticed."],
        ],
    },
    "guided-chat": {
        "chapter": "DAY 1 · A conversation for two", "eyebrow": "Icebreaker countdown / 18:31",
        "title": "Get to know them before asking to team up",
        "text": "You've chosen your icebreaker partner. Start with names, why you came, or something happening nearby. After a real exchange, decide how to invite them to prepare tonight's dinner.",
        "action": "Your partner's portrait lights up. They're waiting for you to speak.",
        "mediaCue": "The chosen guest pauses what they're doing and turns to begin a first conversation with you.",
        "choices": [
            ["Ask them directly to team up with me", "Be clear and leave room for their answer."],
            ["Ask what they'd like to do, then decide together", "Make the division of work a shared decision."],
            ["Suggest doing just this one task tonight", "Keep it easy and leave room to get to know each other."],
        ],
    },
    "team-up": {
        "chapter": "DAY 1 · Your first team", "eyebrow": "Dinner preparations / 19:10",
        "title": "First dinner. First time working together.",
        "text": "Tonight isn't a contest. You and your new partner need to finish one shared task before dinner. The care, persistence, and little frictions of working together can reveal more than an introduction.",
        "action": "Task lights come on in the kitchen, at the supplies table, and beside the terrace setup.",
        "mediaCue": "Pairs prepare food, set the table, or check supplies while other guests pass by.",
        "gameBrief": {
            "name": "Your first dinner partner",
            "format": "Choose food prep, table setting, or checking drinks with your icebreaker partner. Finish together before dinner begins.",
            "winCondition": "Both of you do the part you agreed to. At the end, say how you'd like to work together next time.",
            "strategyPrompt": "How will you work with your partner?",
            "strategyOptions": ["Split the work and handle one half each", "Talk as you work and swap tasks when needed", "Take the harder part and ask them to cover the rest"],
        },
        "choices": [
            ["Split the tasks and take one half each", "Work efficiently and see how each person follows through."],
            ["Stay together and talk as we work", "More time together may also bring a little friction."],
            ["Take the harder part first", "Show up through action without doing everything for them."],
        ],
    },
    "anonymous-letter": {
        "chapter": "DAY 1 · Heart messages", "eyebrow": "Heart inbox / 22:30",
        "title": "Who do you want to know better tomorrow?",
        "text": "Before bed, each guest can send an anonymous heart message to the person they most want to keep getting to know. The show reveals how many messages each person received, but not who sent them. One message is today's choice, not a promise.",
        "action": "Eight phones light up at once. Each has room for one recipient.",
        "mediaCue": "At night, guests compose anonymous messages in their rooms and wait for a notification.",
        "choices": [],
    },
    "callback": {
        "chapter": "DAY 2 · Morning echoes", "eyebrow": "Breakfast by the sea / 07:18",
        "title": "A word from last night stays with you",
        "text": "The messages haven't decided anyone's relationship. But this morning's seats, glances, and next invitations carry something new. Your seven days and six nights have only just begun.",
        "action": "At the breakfast table, someone gently pulls out the neighboring chair.",
        "mediaCue": "Morning breakfast by the sea, a message notification, and a glance from last night's recipient.",
        "choices": [],
    },
}

def bind(source, target):
    if isinstance(source, str) and isinstance(target, str):
        copy[source] = target
    elif isinstance(source, dict) and isinstance(target, dict):
        for key in target:
            if key in source: bind(source[key], target[key])
    elif isinstance(source, (list, tuple)) and isinstance(target, (list, tuple)):
        for left, right in zip(source, target): bind(left, right)

for node_id, target in STORY.items():
    source = g.NODES[node_id]
    bind(source, {key: value for key, value in target.items() if key != "choices"})
    for choice, (label, hint) in zip(source["choices"], target["choices"]):
        bind(choice, {"label": label, "hint": hint})
    # Runtime beat splitting of the fallback body uses these exact substrings.
    source_beats = g.split_story_beats(source["text"])
    target_beats = target.get("textBeats") or [target["text"]]
    if len(source_beats) == len(target_beats): bind(source_beats, target_beats)
    else:
        for index, beat in enumerate(source_beats):
            copy[beat] = target_beats[index] if index < len(target_beats) else ""

destination = ROOT / "content" / "locales" / "en-story.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(copy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(copy)} authored story translations")
