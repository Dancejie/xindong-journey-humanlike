"""Character-specific English introductions; no new biographies or plot events."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import game_content as g, agent_prompt as a
from backend.localization import translate_text, english_copy

# Each row keeps the existing card's public background and personal reason.
# The two undisclosed jobs remain undisclosed; their known hobbies are used.
ROWS = {
 "shenmo": ["I'm a VP in investment banking", "I'm used to thinking things through before speaking", "I joined because I want to tell someone how I feel even before I have every answer", "What do you worry people will get wrong about you on day one?"],
 "linyu": ["I'm an architectural engineer", "I usually look after everyone else first", "I came here to meet someone who asks how I'm doing, too", "What's one small thing you wished someone would help with when you arrived?"],
 "chengye": ["I run an extreme-sports brand", "I tend to move faster than I talk", "I joined to get to know someone seriously and follow through on what I say", "What's one thing you'd like us to try together?"],
 "guyan": ["I'm a game designer and also freelance", "Small talk isn't really my strength", "I'm here to try being honest without waiting for a perfect answer", "Are you more worried about awkward silence or being asked too much too soon?"],
 "jiangwan": ["I'm a counselor", "At work, I spend a lot of time listening", "I came here to let people get to know me outside my work, without analyzing everyone", "Who did you first want to talk to when you walked in?"],
 "jiangmi": ["I keep audio diaries and turn chance encounters into little stories", "I can keep a room lively", "I'm here to see whether sitting quietly with someone can feel just as good", "Did you notice the waves, the suitcase wheels, or someone's hello first?"],
 "sunnian": ["I'm an illustrator", "I'm good at getting everyone settled", "I joined because I'd like someone to care for me sometimes, rather than always being the one helping", "What home-cooked dish would you like for dinner?"],
 "chensu": ["I like repairing old cameras and broken little things", "I don't usually say much", "I came here to practice explaining things instead of expecting people to guess", "What's something you'd like us to make or do together this week?"],
 "luyao": ["I lead a smart-hardware product team", "I usually work out a route through a complicated problem first", "I'm here to share what I feel with someone while I'm still making up my mind", "What would you most like people to understand about you?"],
 "yecheng": ["I restore old books", "I tend to notice the traces people leave in words and objects", "I joined to say what I want sooner and meet someone who cares for me in return", "What's one small thing that helps you settle into a new place?"],
 "tangli": ["I'm a field producer for outdoor documentaries", "I usually jump into action quickly", "I came here to make choices together and say when I'm tired", "What would you like to try outdoors together?"],
 "wenxu": ["I research urban climate data", "I sometimes revise my answer while I'm talking", "I'm here to get to know someone honestly, even when I haven't worked everything out", "What's something you don't have a finished answer to yet?"],
 "hechuan": ["I'm a documentary editor", "I pay attention to what people leave unfinished", "I joined so someone could hear my own preferences, instead of always being the listener", "What would you like someone to ask you about?"],
 "peiran": ["I curate experiences for a children's museum", "I like turning ordinary things into little games", "I came here to find out whether two people can be comfortable after the excitement dies down", "What's one ordinary thing you'd turn into a game?"],
 "lichuan": ["I manage food and beverage operations at a boutique hotel", "I'm used to keeping the whole table running smoothly", "I'm here to meet someone who shares the work and notices me as a person", "Which part of making dinner would you like to take?"],
 "qiaolan": ["I'm a stage-mechanics engineer", "When something needs doing, I tend to act first", "I joined to practice asking people before I act and explaining what matters", "What would you like to do together before dinner?"],
 "shaozheng": ["I coordinate production for touring live performances", "In a sudden problem, I usually put the steps in order", "I came here to meet someone who points out what I've missed before I make the decision", "What would you like to start with on your first day?"],
 "qince": ["I lead digital products for cross-border public services", "I ask who's affected before deciding what to do", "I'm here to find out whether someone still wants me around when I'm not solving a problem", "What would you like to start with on your first day?"],
 "jiheng": ["I design interactive exhibits for science museums", "I tend to spot another possibility quickly", "I joined because I'd like someone to notice what I finish, too, rather than just my next idea", "What would you like to start with on your first day?"],
 "xiache": ["I'm a fact-checking editor for an investigative podcast", "My first question is often whose side of the story is missing", "I came here for a relationship I don't have to keep analyzing for its value", "What would you like to start with on your first day?"],
 "zhouyan": ["I'm a community film curator", "I can listen patiently to different interpretations", "I'm here to meet someone who discusses what I value seriously, without turning it into a romantic ideal", "What would you like to start with on your first day?"],
 "ningzhi": ["I'm an illustrator specializing in accessible travel", "I notice whether a space lets people make choices", "I joined because I'd like people to ask me directly rather than kindly arrange everything for me", "What would you like to start with on your first day?"],
 "xuhang": ["I'm a rehearsal coach for a youth theater", "I tend to invite the quiet person into the conversation", "I came here to meet someone who approaches me even when I'm not hosting", "What would you like to start with on your first day?"],
 "gutang": ["I run community sports programs", "I can usually help a beginner feel ready to join in", "I'm here to meet someone who invites me sometimes, even when I'm not leading the group", "What would you like to start with on your first day?"],
 "yanxu": ["I'm a civil-aviation safety auditor", "When I agree to a time, I write it down", "I joined to learn that a changed plan doesn't have to mean a failed relationship", "What would you like to start with on your first day?"],
 "jianning": ["I advise on restoration costs and materials for historic buildings", "I like to make sure we're using the same numbers and assumptions", "I'm here to meet someone I can ask for help without being treated as less capable", "What would you like to start with on your first day?"],
 "luozheng": ["I lead catering supply-chain operations for festivals", "I check what's available before we talk about what we'd like", "I came here to meet someone who doesn't always leave me to cover the gap first", "What would you like to start with on your first day?"],
 "chengqing": ["I'm an operations director for city road races", "I put safety before the experience", "I joined to meet people I can tell when I can't fix everything today", "What would you like to start with on your first day?"],
 "xiemu": ["I'm a nature sound recordist", "I listen to a place before I do much else", "I'm here to meet someone who doesn't mistake being quiet for being cold", "What would you like to start with on your first day?"],
 "yaoyin": ["I'm a special-effects makeup artist for film and television", "I ask how something feels before I start working", "I came here to have my work understood as storytelling, rather than just beauty", "What would you like to start with on your first day?"],
 "hanxi": ["I teach first aid for children and families", "I can usually help a nervous person try one first step", "I joined to meet someone who believes my serious side, even when I'm keeping things light", "What would you like to start with on your first day?"],
 "luoxing": ["I'm a food-truck chef", "I can change a dish after one taste of feedback", "I'm here to meet someone who seeks me out even when I'm not cooking", "What would you like to start with on your first day?"],
}

HONEST_REASONS = {
 'linyu': "I'm here to find out whether someone notices when I'm the one who needs a hand",
 'chengye': "I joined to stay in an honest conversation when making another joke would be easier",
 'guyan': "I came here to meet someone before I've figured out what to say next",
 'jiangwan': "This week, I came to be known for something beyond listening to other people",
 'jiangmi': "I'm here to meet someone who won't get up the moment I stop filling the silence",
 'sunnian': "I joined to meet someone who still wants my company when I'm not organizing everything",
 'chensu': "I joined to let someone hear what I mean, instead of fixing something and leaving the explanation unsaid",
 'tangli': "I came here to choose a slower pace with someone, and admit it when I've had enough for one day",
 'chengqing': "I came here for a relationship where saying 'I can't manage that' doesn't mean I've let everyone down",
}

translations = {}
for card in g.CHARACTER_CARDS:
 a._ensure_public_intro_contract(card)
 cid = card['id']; name = translate_text(card['names']['primary']); mbti = card['mbti']
 background, mask, reason, question = ROWS[cid]
 facts = card.get('sourceProfile',{}).get('facts',{})
 occupation = str(facts.get('occupation') or '')
 if occupation and not any(term in occupation for term in ('待剧情','待正式确认','运行时职业待','待公开')):
  job = translate_text(occupation).lower()
  article = 'an' if job[0] in 'aeiou' else 'a'
  background = f"I work as {article} {job}"
 age = f", {facts['age']}" if isinstance(facts.get('age'),int) else ''
 prefix = f"I'm {name}{age}, an {mbti}. {background}."
 modes = {
  'intro-clear': f"Hi, everyone. {prefix} {reason}.",
  'intro-question': f"{name}, {mbti}. {background}. I came here to get to know people at my own pace. {question}",
  'intro-honest': f"{mask}. You can call me {name}; I'm an {mbti}. {background}. {HONEST_REASONS.get(cid, reason)}.",
 }
 for choice_id, (source, hint) in g.INTRODUCTION_FALLBACKS[cid].items():
  translations[source] = modes[choice_id]
  translations[hint] = {
   'intro-clear':'Share your name, background, and why you joined.',
   'intro-question':'Offer something about yourself, then invite an answer.',
   'intro-honest':'Say something honest about what you hope to find here.',
  }[choice_id]
 if cid in a.PUBLIC_CHAT_PREFIXES:
  translations[a.PUBLIC_CHAT_PREFIXES[cid]] = f"I'm {name}, an {mbti}. {background}."
 if cid in a.PUBLIC_CHAT_INTROS: translations[a.PUBLIC_CHAT_INTROS[cid]] = f"{mask}. {reason}."
 impression, hint = g.CAST_FIRST_IMPRESSION_FALLBACKS[cid]
 translations[impression] = f"I remember {name}'s introduction: “{reason}.”"
 translations[hint] = "At dinner, I'd like to see how that comes through when we do something together."

# Case-insensitive English anchors used only by semantic intro checks.
anchors = {
 '投行':'investment banking', '建筑':'architectural', '极限运动':'extreme-sports', '品牌':'brand',
 '游戏策划':'game designer', '外包':'freelance', '心理咨询':'counselor', '声音日记':'audio diaries',
 '录音':'audio', '插画':'illustrator', '旧相机':'old cameras', '修':'repair', '智能硬件':'smart-hardware',
 '产品':'product', '古籍':'rare-book', '修复':'conserv', '户外纪录片':'outdoor documentaries',
 '现场制片':'field producer', '城市气候':'urban climate', '数据':'data', '纪录片':'documentary',
 '剪辑':'editor', '儿童博物馆':"children's museum", '体验策展':'curate experiences',
 '精品酒店':'boutique hotel', '餐饮运营':'food and beverage', '舞台机械':'stage-mechanics', '工程':'engineer',
 '平时':'usually', '喜欢':'like', '日常':'everyday', '感受':'feel', '慢一点':'slow', '认识':'know',
 '真实':'honest', '照顾':'care', '被对待':'treated', '认真':'seriously', '约定':'promise',
 '陪一个人':'with someone', '诚实':'honest', '真话':'truth', '相处':'together', '自己':'myself',
 '被听见':'heard', '被理解':'understood', '安静':'quiet', '相遇':'meet', '心动':'spark', '故事':'stories',
 '被照顾':'cared for', '被记住':'remembered', '不只会照顾':'more than helping', '说清楚':'explain',
 '解释':'explain', '改变主意':'mind', '偏好':'preferences', '互相照顾':'in return', '说不':'no',
 '一起决定':'choices together', '关系':'relationship', '不完整':'unfinished', '表达':'share',
 '被问':'asks', '留下':'stay', '一起':'together', '分担':'shares', '看见':'notices', '等':'wait',
 '说清':'explain', '误会':'mistake',
}
translations.update(anchors)
path = ROOT/'content/locales/en-fallbacks.json'
path.write_text(json.dumps(translations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Wrote {len(translations)} character-specific fallback translations')
