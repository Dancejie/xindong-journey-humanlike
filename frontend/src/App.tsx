import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { Icon } from './ui/Icon'
import './styles.css'

type Character = {
  id: string; name: string; mbti: string; tagline: string; accent: string
  portrait: string; video: string; publicMask: string; privateFear: string
  memorySeed: string; voice: string; boundary: string; quickPrompts: string[]
  independentInterest: string; eventLabel: string
  age?: number | string; occupation?: string; publicFacts?: { occupation?: string; publicPersona?: string }
  gender?: '男性' | '女性' | string; mediaStatus?: 'ready' | 'planned' | string; mediaFallbackKind?: string
  opener?: ChatOpener | string; openingLine?: string; suggestedPrompts?: ChatSuggestionInput[]
  isPlayerPerspective?: boolean; chatEnabled?: boolean; isGuidedTarget?: boolean
  location?: string; availableAtLocations?: string[]; groupChatEnabled?: boolean
}

type SceneIdentityCard = {
  characterId?: string; id?: string; name: string; mbti: string
  occupation?: string; age?: number | string; tagline?: string; accent?: string
}

type SceneIdentityTimeline = {
  characterId: string; startSeconds: number; endSeconds: number
}

type Memory = {
  id: string; characterId: string; playerText: string; agentReply: string
  intentId: string; affectionDelta: number; trustDelta: number; createdAt: string
  attitude: string; stageDirection?: string; summary?: string
  relationshipDelta: Record<string, number>
  suggestions?: ChatSuggestionInput[]; suggestedPrompts?: ChatSuggestionInput[]
  suggestionsSource?: 'deepseek' | 'engine-fallback' | string
  time?: string; locationId?: string; locationName?: string; channel?: '1v1' | 'group' | string
  participantIds?: string[]; participantNames?: string[]; conversationId?: string
}

type HeartMessage = {
  id?: string; text: string; isAnonymous?: boolean
  senderCharacterId?: string; recipientCharacterId?: string; sentAt?: string; receivedAt?: string; day?: number
}

type ConversationContext = {
  version?: string; conversationId?: string; time?: string
  locationId?: string; locationName?: string; participantIds?: string[]; channel?: '1v1' | 'group'
}

type ChatVenueCharacter = { id: string; name: string; mbti: string }
type ChatVenue = {
  locationId: string; locationName: string; time?: string; supportsGroup: boolean
  characters: ChatVenueCharacter[]
}
type ChatContexts = { scene?: ConversationContext; venues: ChatVenue[]; revision?: number }

type GroupReply = {
  characterId: string; characterName: string; reply: string; stageDirection?: string
}

type RelationshipAxes = { trust: number; affection: number; respect: number; fear: number; debt: number; attraction: number; resentment: number }
type StoryEvent = { eventId: string; characterId: string; label: string; text: string }
type StoryMission = {
  id: string; eventId: string; title: string; bridgeText: string; prompt: string
  objective: string; deadline: string; successEvidence: string; exit: string
  sceneSetup?: string; reversalBeat?: string; characterInsight?: string; visualCue?: string; availableStrategies?: string[]
  participantIds: string[]; urgency: 'low' | 'medium' | 'high'; status: 'active'
  media?: {
    assetId?: string; src?: string; poster?: string; durationSeconds?: number
    available?: boolean; status?: 'ready' | 'planned' | string
    fallback?: { kind?: string; src?: string; poster?: string }
    identityCards?: SceneIdentityCard[]; identityTimeline?: SceneIdentityTimeline[]
  }
}

type PendingChat = boolean | string | {
  id?: string; characterId?: string; targetCharacterId?: string; guidedTargetCharacterId?: string
  autoOpen?: boolean; label?: string; status?: 'required' | 'completed' | string
  requiredTurnCount?: number; completedTurnCount?: number; reason?: string
}

type SuggestionKind = 'followup' | 'mainline' | 'deeper'
type ChatSuggestionInput = string | {
  text?: string; prompt?: string; value?: string; message?: string; content?: string
  type?: SuggestionKind | string; kind?: SuggestionKind | string; category?: SuggestionKind | string
  suggestionType?: SuggestionKind | string; intent?: SuggestionKind | string
  label?: string; displayLabel?: string
}
type SuggestedPrompt = { text: string; kind: SuggestionKind; label: string }

type ChatOpener = {
  stageDirection?: string; line?: string; dialogue?: string; suggestedPrompts?: ChatSuggestionInput[]
}

type ChatOpenerPayload = {
  opener?: ChatOpener | string; openingLine?: string; stageDirection?: string
  dialogue?: string; line?: string; suggestedPrompts?: ChatSuggestionInput[]; prompts?: ChatSuggestionInput[]; suggestions?: ChatSuggestionInput[]
}

type Snapshot = {
  runId: string; revision: number; nodeId: string
  player: { mbti: string; displayName: string; gender?: string; perspectiveCharacterId?: string }
  castIds?: string[]
  mediaRotation?: { slot?: string; leadGender?: string; anchorCharacterId?: string; selectionBucket?: string[]; eventId?: string | null }
  flags: { heat: number; clarity: number; publicImpression: number }
  affection: Record<string, number>; trust: Record<string, number>
  relationships: Record<string, RelationshipAxes>; attitudes: Record<string, string>
  eventLedger: StoryEvent[]; activeEventId: string | null
  storyArc: { phase: 'early' | 'middle' | 'late'; beatCount: number; activeMissionId: string | null; tension: number; reciprocity: number; uncertainty: number }
  storyEventLedger: unknown[]; storyMission: StoryMission | null
  focusCharacterId: string | null; letterRecipientId: string | null
  echoMemories: Memory[]; choiceHistory: unknown[]
  guidedTargetCharacterId?: string | null; pendingChat?: PendingChat | null
  pendingInteraction?: PendingChat | null
  chatOpeners?: Record<string, ChatOpenerPayload>
  sceneContext?: ConversationContext
  characterPresence?: Record<string, string>
  heartMailbox?: { sent?: HeartMessage[]; received?: HeartMessage[] }
}

type Choice = { id: string; label: string; hint: string; characterId?: string; targetCharacterId?: string }
type StoryNode = {
  chapter: string; eyebrow: string; title: string; speaker: string; text: string
  textBeats?: string[]
  characterId?: string; speakerCharacterId?: string; cinematic?: string; choices: Choice[]
  sceneVideo?: string; backgroundVideo?: string; poster?: string
  media?: {
    assetId?: string; src?: string; poster?: string; available?: boolean
    status?: 'ready' | 'planned' | string
    fallback?: { kind?: string; src?: string; poster?: string }
    identityCards?: SceneIdentityCard[]; identityTimeline?: SceneIdentityTimeline[]
  }
  mediaCue?: string; action?: string; eventId?: string
  gameBrief?: { name: string; format: string; winCondition: string }
  requiresMemory?: boolean; requiresEvent?: boolean; requiresGuidedInteraction?: boolean; characterChoice?: boolean; isEnding?: boolean
  allowDirector?: boolean
  guidedTargetCharacterId?: string | null; pendingChat?: PendingChat | null
  guidedInteraction?: PendingChat | null
  location?: string; time?: string
}
type View = {
  snapshot: Snapshot; node: StoryNode; characters: Character[]
  guidedTargetCharacterId?: string | null; pendingChat?: PendingChat | null
  chatOpeners?: Record<string, ChatOpenerPayload>
  chatContexts?: ChatContexts
}
type Receipt = { kind: string; intentId?: string; attitude?: string; publicReason?: string; patch?: Record<string, unknown>; eventActivation?: StoryEvent | null; mission?: StoryMission; title?: string; playerMissionPrompt?: string }

const PROGRESS: Record<string, number> = { 'arrival-context': 6, 'villa-arrival': 18, introductions: 32, 'cast-first-impressions': 41, 'icebreaker-choice': 49, 'guided-chat': 62, 'team-up': 76, 'anonymous-letter': 89, callback: 100, arrival: 8, 'first-look': 26, 'private-window': 48, 'event-reveal': 68 }
const ATTITUDE_LABELS: Record<string, string> = { warm: '温暖', curious: '好奇', guarded: '戒备', challenging: '试探', vulnerable: '袒露', softened: '松动', uncertain: '迟疑', honest: '坦诚', moved: '被触动', careful: '谨慎', steady: '稳定', boundary: '边界' }
const AXIS_LABELS: Record<string, string> = { trust: '信任', affection: '好感', respect: '尊重', fear: '压力', debt: '亏欠', attraction: '吸引', resentment: '芥蒂' }

// Keep the currently published public card shape forward-compatible with the
// richer Day 1 cast payload. Two source cards intentionally do not disclose a
// confirmed occupation yet; the UI says so instead of inventing one.
const PUBLIC_OCCUPATION_FALLBACK: Record<string, string> = {
  shenmo: '投行 VP',
  linyu: '建筑工程师',
  chengye: '极限运动品牌创始人',
  guyan: '游戏策划',
  jiangwan: '心理咨询师',
  jiangmi: '职业待公开',
  sunnian: '插画师',
  chensu: '职业待公开',
}

function identityId(identity: Character | SceneIdentityCard) {
  return 'characterId' in identity && identity.characterId ? identity.characterId : identity.id
}

function publicOccupation(identity: Character | SceneIdentityCard) {
  const id = identityId(identity)
  const publicFacts = 'publicFacts' in identity ? identity.publicFacts : undefined
  const occupation = identity.occupation || publicFacts?.occupation || (id ? PUBLIC_OCCUPATION_FALLBACK[id] : undefined)
  if (!occupation || /待剧情|待正式确认|运行时职业待|原稿为/.test(occupation)) return '职业待公开'
  return occupation
}

function identityCardFromCharacter(character: Character): SceneIdentityCard {
  return {
    characterId: character.id,
    name: character.name,
    mbti: character.mbti,
    age: character.age,
    occupation: publicOccupation(character),
    tagline: character.tagline,
    accent: character.accent,
  }
}

type SceneMediaAsset = {
  assetId: string; src?: string; poster?: string; fallbackSrc: string; fallbackPoster?: string; cue?: string
  identityCards?: SceneIdentityCard[]; identityTimeline?: SceneIdentityTimeline[]
}

const NODE_MEDIA: Record<string, SceneMediaAsset> = {
  'arrival-context': { assetId: 'D1-A1-island-hotel-establish', src: '/media/video/D1-A1-island-hotel-establish.mp4', poster: '/media/posters/D1-A1-island-hotel-establish.jpg', fallbackSrc: '/media/video/D1-A1-island-hotel-establish.mp4', fallbackPoster: '/media/posters/D1-A1-island-hotel-establish.jpg' },
  'villa-arrival': { assetId: 'D1-A2-villa-entry', src: '/media/video/D1-A2-villa-entry.mp4', poster: '/media/posters/D1-A2-villa-entry.jpg', fallbackSrc: '/media/video/D1-A2-villa-entry.mp4', fallbackPoster: '/media/posters/D1-A2-villa-entry.jpg' },
  introductions: { assetId: 'D1-A3-cast-introductions', src: '/media/video/D1-A3-cast-introductions.mp4', poster: '/media/posters/D1-A3-cast-introductions.jpg', fallbackSrc: '/media/video/D1-A3-cast-introductions.mp4', fallbackPoster: '/media/posters/D1-A3-cast-introductions.jpg' },
  'cast-first-impressions': { assetId: 'D1-A3B-cast-first-impressions', src: '/media/video/D1-A3B-cast-first-impressions.mp4', poster: '/media/posters/D1-A3B-cast-first-impressions.jpg', fallbackSrc: '/media/video/D1-A3B-cast-first-impressions.mp4', fallbackPoster: '/media/posters/D1-A3B-cast-first-impressions.jpg' },
  'icebreaker-choice': { assetId: 'D1-A4-icebreaker-selection', src: '/media/video/D1-A4-icebreaker-selection.mp4', poster: '/media/posters/D1-A4-icebreaker-selection.jpg', fallbackSrc: '/media/video/D1-A4-icebreaker-selection.mp4', fallbackPoster: '/media/posters/D1-A4-icebreaker-selection.jpg' },
  'guided-chat': { assetId: 'D1-A5-guided-smalltalk', src: '/media/video/D1-A5-guided-smalltalk.mp4', poster: '/media/posters/D1-A5-guided-smalltalk.jpg', fallbackSrc: '/media/video/D1-A5-guided-smalltalk.mp4', fallbackPoster: '/media/posters/D1-A5-guided-smalltalk.jpg' },
  'team-up': { assetId: 'D1-A6-first-dinner-team', src: '/media/video/D1-A6-first-dinner-team.mp4', poster: '/media/posters/D1-A6-first-dinner-team.jpg', fallbackSrc: '/media/video/D1-A6-first-dinner-team.mp4', fallbackPoster: '/media/posters/D1-A6-first-dinner-team.jpg' },
  'anonymous-letter': { assetId: 'D1-A7-heart-message', src: '/media/video/D1-A7-heart-message.mp4', poster: '/media/posters/D1-A7-heart-message.jpg', fallbackSrc: '/media/video/D1-A7-heart-message.mp4', fallbackPoster: '/media/posters/D1-A7-heart-message.jpg' },
  callback: { assetId: 'D2-A1-memory-callback', src: '/media/video/D2-A1-memory-callback.mp4', poster: '/media/posters/D2-A1-memory-callback.jpg', fallbackSrc: '/media/video/D2-A1-memory-callback.mp4', fallbackPoster: '/media/posters/D2-A1-memory-callback.jpg' },
}

// Every authored Story Director event has a deterministic stage projection. Its
// fallback remains bound to the same event asset, so a failed load can never
// substitute unrelated story footage.
const EVENT_MEDIA: Record<string, SceneMediaAsset> = {
  'story.kitchen.two-person-shift': { assetId: 'EV-KITCHEN-two-person-shift', src: '/media/video/EV-KITCHEN-two-person-shift.mp4', poster: '/media/posters/EV-KITCHEN-two-person-shift.jpg', fallbackSrc: '/media/video/EV-KITCHEN-two-person-shift.mp4', fallbackPoster: '/media/posters/EV-KITCHEN-two-person-shift.jpg' },
  'story.house.rules-friction': { assetId: 'EV-RULES-house-friction', src: '/media/video/EV-RULES-house-friction.mp4', poster: '/media/posters/EV-RULES-house-friction.jpg', fallbackSrc: '/media/video/EV-RULES-house-friction.mp4', fallbackPoster: '/media/posters/EV-RULES-house-friction.jpg' },
  'story.signal.first-anonymous-message': { assetId: 'EV-SIGNAL-first-anonymous-message', src: '/media/video/EV-SIGNAL-first-anonymous-message.mp4', poster: '/media/posters/EV-SIGNAL-first-anonymous-message.jpg', fallbackSrc: '/media/video/EV-SIGNAL-first-anonymous-message.mp4', fallbackPoster: '/media/posters/EV-SIGNAL-first-anonymous-message.jpg' },
  'story.identity.profession-reveal': { assetId: 'EV-IDENTITY-profession-reveal', src: '/media/video/EV-IDENTITY-profession-reveal.mp4', poster: '/media/posters/EV-IDENTITY-profession-reveal.jpg', fallbackSrc: '/media/video/EV-IDENTITY-profession-reveal.mp4', fallbackPoster: '/media/posters/EV-IDENTITY-profession-reveal.jpg' },
  'story.date.blind-box': { assetId: 'EV-DATE-blind-box', src: '/media/video/EV-DATE-blind-box.mp4', poster: '/media/posters/EV-DATE-blind-box.jpg', fallbackSrc: '/media/video/EV-DATE-blind-box.mp4', fallbackPoster: '/media/posters/EV-DATE-blind-box.jpg' },
  'story.date.mutual-signal': { assetId: 'EV-DATE-mutual-signal', src: '/media/video/EV-DATE-mutual-signal.mp4', poster: '/media/posters/EV-DATE-mutual-signal.jpg', fallbackSrc: '/media/video/EV-DATE-mutual-signal.mp4', fallbackPoster: '/media/posters/EV-DATE-mutual-signal.jpg' },
  'story.missed-timing.empty-seat': { assetId: 'EV-MISSED-empty-seat', src: '/media/video/EV-MISSED-empty-seat.mp4', poster: '/media/posters/EV-MISSED-empty-seat.jpg', fallbackSrc: '/media/video/EV-MISSED-empty-seat.mp4', fallbackPoster: '/media/posters/EV-MISSED-empty-seat.jpg' },
  'story.care.breakfast-callback': { assetId: 'EV-CARE-breakfast-callback', src: '/media/video/EV-CARE-breakfast-callback.mp4', poster: '/media/posters/EV-CARE-breakfast-callback.jpg', fallbackSrc: '/media/video/EV-CARE-breakfast-callback.mp4', fallbackPoster: '/media/posters/EV-CARE-breakfast-callback.jpg' },
  'story.triangle.reverse-invite': { assetId: 'EV-TRIANGLE-reverse-invite', src: '/media/video/EV-TRIANGLE-reverse-invite.mp4', poster: '/media/posters/EV-TRIANGLE-reverse-invite.jpg', fallbackSrc: '/media/video/EV-TRIANGLE-reverse-invite.mp4', fallbackPoster: '/media/posters/EV-TRIANGLE-reverse-invite.jpg' },
  'story.challenge.water-bridge': { assetId: 'EV-BRIDGE-hidden-courage', src: '/media/video/EV-BRIDGE-hidden-courage.mp4', poster: '/media/posters/EV-BRIDGE-hidden-courage.jpg', fallbackSrc: '/media/video/EV-BRIDGE-hidden-courage.mp4', fallbackPoster: '/media/posters/EV-BRIDGE-hidden-courage.jpg' },
  'story.group.truth-firepit': { assetId: 'EV-GROUP-truth-firepit', src: '/media/video/EV-GROUP-truth-firepit.mp4', poster: '/media/posters/EV-GROUP-truth-firepit.jpg', fallbackSrc: '/media/video/EV-GROUP-truth-firepit.mp4', fallbackPoster: '/media/posters/EV-GROUP-truth-firepit.jpg' },
  'story.bombshell.ninth-card': { assetId: 'EV-BOMBSHELL-ninth-card', src: '/media/video/EV-BOMBSHELL-ninth-card.mp4', poster: '/media/posters/EV-BOMBSHELL-ninth-card.jpg', fallbackSrc: '/media/video/EV-BOMBSHELL-ninth-card.mp4', fallbackPoster: '/media/posters/EV-BOMBSHELL-ninth-card.jpg' },
  'story.past.consent-reveal': { assetId: 'EV-PAST-consent-reveal', src: '/media/video/EV-PAST-consent-reveal.mp4', poster: '/media/posters/EV-PAST-consent-reveal.jpg', fallbackSrc: '/media/video/EV-PAST-consent-reveal.mp4', fallbackPoster: '/media/posters/EV-PAST-consent-reveal.jpg' },
  'story.trip.last-two-days': { assetId: 'EV-TRIP-last-two-days', src: '/media/video/EV-TRIP-last-two-days.mp4', poster: '/media/posters/EV-TRIP-last-two-days.jpg', fallbackSrc: '/media/video/EV-TRIP-last-two-days.mp4', fallbackPoster: '/media/posters/EV-TRIP-last-two-days.jpg' },
  'story.final.unsent-letter': { assetId: 'EV-FINAL-unsent-letter', src: '/media/video/EV-FINAL-unsent-letter.mp4', poster: '/media/posters/EV-FINAL-unsent-letter.jpg', fallbackSrc: '/media/video/EV-FINAL-unsent-letter.mp4', fallbackPoster: '/media/posters/EV-FINAL-unsent-letter.jpg' },
  'story.final.confession-day': { assetId: 'EV-FINAL-confession-day', src: '/media/video/EV-FINAL-confession-day.mp4', poster: '/media/posters/EV-FINAL-confession-day.jpg', fallbackSrc: '/media/video/EV-FINAL-confession-day.mp4', fallbackPoster: '/media/posters/EV-FINAL-confession-day.jpg' },
}

const FALLBACK_OPENERS: Record<string, { stageDirection: string; line: string }> = {
  shenmo: { stageDirection: '沈墨把座位卡向旁边挪了一点，给你留出空位。', line: '你好，我是沈墨。刚才大家介绍得都很快，我可能比较容易记住细节。你进门后最先注意到了什么？' },
  linyu: { stageDirection: '林屿给你倒了半杯温水，才在对面坐下。', line: '你好，我是林屿。先喝口水吧，一路过来应该挺累的。你现在还紧张吗？' },
  chengye: { stageDirection: '程野靠住椅背，笑着把镜头外的空位指给你。', line: '程野。刚才镜头太多，都没来得及好好打招呼。先不谈任务——这间小屋里，你最想去哪里看看？' },
  guyan: { stageDirection: '顾言放下手里的机械锁，像是在认真组织第一句话。', line: '你好，我是顾言。自我介绍这件事我不太擅长，不过我会认真听。你希望别人先认识你的哪一面？' },
  jiangwan: { stageDirection: '江晚合上写到一半的信纸，抬眼看向你。', line: '你好，我是江晚。刚才人多，很多话只来得及说一半。现在只有我们，你想从哪件小事开始聊？' },
  jiangmi: { stageDirection: '姜米把录音笔按下暂停，朝你晃了晃手。', line: '我是姜米。这里的海风比我想象中还大，但好像也比想象中更容易让人开口。你刚到小屋的第一感觉是什么？' },
  sunnian: { stageDirection: '苏念把果盘往你面前推了推，确认你坐得舒服才开口。', line: '你好，我是苏念。刚才一直在忙，都忘了问你有没有吃好。第一天还习惯吗？' },
  chensu: { stageDirection: '陈叙确认旧相机放稳了，拉开旁边的椅子。', line: '陈叙。刚把东西放好。你要是不介意，先坐会儿——刚来这里，还习惯吗？' },
}

function getClientId() {
  const key = 'heart-journey-public-client-id'
  try {
    const saved = localStorage.getItem(key)
    if (saved) return saved
    const created = globalThis.crypto?.randomUUID?.() || `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`
    localStorage.setItem(key, created)
    return created
  } catch {
    return `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`
  }
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', 'X-Client-Id': getClientId(), ...(options?.headers || {}) },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || '心动信号暂时中断，请稍后重试')
  return payload
}

function pendingCharacterId(pending?: PendingChat | null) {
  if (typeof pending === 'string') return pending
  if (!pending || typeof pending !== 'object') return null
  return pending.characterId || pending.targetCharacterId || pending.guidedTargetCharacterId || null
}

function resolveGuidedCharacterId(view: View) {
  return view.guidedTargetCharacterId
    || view.snapshot.guidedTargetCharacterId
    || view.node.guidedTargetCharacterId
    || pendingCharacterId(view.pendingChat)
    || pendingCharacterId(view.snapshot.pendingChat)
    || pendingCharacterId(view.node.pendingChat)
    || pendingCharacterId(view.snapshot.pendingInteraction)
    || pendingCharacterId(view.node.guidedInteraction)
    || null
}

function resolvePendingChat(view: View) {
  return view.pendingChat ?? view.snapshot.pendingChat ?? view.node.pendingChat ?? view.snapshot.pendingInteraction ?? view.node.guidedInteraction ?? null
}

function normalizeOpener(payload: ChatOpenerPayload | ChatOpener | string | undefined, fallback: { stageDirection: string; line: string }) {
  if (typeof payload === 'string') return { ...fallback, line: payload }
  if (!payload) return fallback
  const expanded = payload as ChatOpenerPayload & ChatOpener
  const nested = typeof expanded.opener === 'object' ? expanded.opener : undefined
  const nestedLine = typeof expanded.opener === 'string' ? expanded.opener : undefined
  return {
    stageDirection: nested?.stageDirection || expanded.stageDirection || fallback.stageDirection,
    line: nested?.line || nested?.dialogue || nestedLine || expanded.openingLine || expanded.line || expanded.dialogue || fallback.line,
  }
}

function promptsFromPayload(payload?: ChatOpenerPayload | ChatOpener | string) {
  if (!payload || typeof payload === 'string') return []
  const expanded = payload as ChatOpenerPayload & ChatOpener
  const nested = typeof expanded.opener === 'object' ? expanded.opener : undefined
  return nested?.suggestedPrompts || expanded.suggestedPrompts || expanded.prompts || expanded.suggestions || []
}

function suggestionKind(value?: string): SuggestionKind {
  const normalized = value?.toLowerCase().replace(/[_\s-]/g, '')
  if (normalized === 'mainline' || normalized === 'story' || normalized === 'advance' || normalized === '推进剧情') return 'mainline'
  if (normalized === 'deeper' || normalized === 'deep' || normalized === 'memory' || normalized === '深入了解') return 'deeper'
  return 'followup'
}

function normalizeSuggestion(input: ChatSuggestionInput, fallbackKind: SuggestionKind = 'followup'): SuggestedPrompt | null {
  if (typeof input === 'string') {
    const text = input.trim()
    return text ? { text, kind: fallbackKind, label: fallbackKind === 'mainline' ? '推进剧情' : fallbackKind === 'deeper' ? '深入了解' : '接着聊' } : null
  }
  const text = (input.text || input.prompt || input.value || input.message || input.content || input.label || '').trim()
  if (!text) return null
  const declaredKind = input.type || input.kind || input.category || input.suggestionType || input.intent
  const kind = declaredKind ? suggestionKind(declaredKind) : fallbackKind
  const standardLabel = kind === 'mainline' ? '推进剧情' : kind === 'deeper' ? '深入了解' : '接着聊'
  const label = input.displayLabel || (input.label && input.label !== text ? input.label : standardLabel)
  return { text, kind, label }
}

function fallbackPrompts(character: Character, perspective: Character | undefined, memories: Memory[], phase: Snapshot['storyArc']['phase'], nodeId: string): ChatSuggestionInput[] {
  const playerName = perspective?.name || '我'
  if (!memories.length) return [
    { text: `你好，我是${playerName}。刚才人多，没来得及好好认识你。`, type: 'followup', displayLabel: '先打招呼' },
    { text: '第一次来这种节目，你现在紧张吗？', type: 'deeper' },
    { text: nodeId === 'guided-chat' ? '节目组让我们记住对方一件真实的小事。你最希望我先记住什么？' : '你为什么会来《心动之旅》？', type: 'mainline' },
  ]
  const latest = memories[memories.length - 1]
  if (memories.length === 1 || phase === 'early') return [
    { text: `你还记得我刚才说的“${latest.playerText.slice(0, 24)}”吗？`, type: 'followup', displayLabel: '回忆回声' },
    { text: '和刚见面时比，你现在对我有什么新印象？', type: 'deeper' },
    { text: nodeId === 'guided-chat' ? '接下来的组队，你最想先从哪件事开始？' : (character.quickPrompts[0] || '你愿意和我一起试试下一个任务吗？'), type: 'mainline' },
  ]
  return [
    { text: `上次聊到“${(latest.summary || latest.playerText).slice(0, 22)}”，你后来还想过吗？`, type: 'followup', displayLabel: '回忆回声' },
    { text: character.quickPrompts[0] || '这次你想让我多了解你的哪一面？', type: 'deeper' },
    { text: '如果下一次任务要两个人一起做，你愿意和我试试吗？', type: 'mainline' },
  ]
}

function promptKeepsPlayerIdentity(prompt: string, perspective?: Character) {
  if (!perspective) return true
  const selfIntroduction = prompt.match(/(?:你好[，,。！!\s]*)?我(?:叫|是)\s*([\p{Script=Han}]{2,4})(?=[，,。！!\s]|$)/u)
  return !selfIntroduction || selfIntroduction[1] === perspective.name
}

function selectSuggestedPrompts(inputs: ChatSuggestionInput[], perspective: Character | undefined, firstGreeting?: SuggestedPrompt) {
  const legacyKinds: SuggestionKind[] = ['followup', 'mainline', 'deeper']
  const normalized = inputs
    .map((input, index) => normalizeSuggestion(input, legacyKinds[index % legacyKinds.length]))
    .filter((item): item is SuggestedPrompt => !!item && promptKeepsPlayerIdentity(item.text, perspective))
  const unique = normalized.filter((item, index, list) => list.findIndex(candidate => candidate.text === item.text) === index)
  const selected: SuggestedPrompt[] = []
  if (firstGreeting) selected.push(firstGreeting)
  const kinds: SuggestionKind[] = firstGreeting ? ['mainline', 'deeper', 'followup'] : ['followup', 'mainline', 'deeper']
  kinds.forEach(kind => {
    const candidate = unique.find(item => item.kind === kind && !selected.some(current => current.text === item.text))
    if (candidate && selected.length < 3) selected.push(candidate)
  })
  unique.forEach(item => {
    if (selected.length < 3 && !selected.some(current => current.text === item.text)) selected.push(item)
  })
  return selected.slice(0, 3)
}

function buildNarrationBeats(text: string, authoredBeats?: string[]) {
  const explicit = (authoredBeats || []).map(beat => beat.trim()).filter(Boolean)
  if (explicit.length) return explicit.slice(0, 4)
  const normalized = text.trim()
  if (!normalized || normalized.length <= 68) return [normalized]
  const clauses = normalized.match(/[^，。！？!?；;]+[，。！？!?；;]?/g)?.map(part => part.trim()).filter(Boolean) || [normalized]
  const desiredCount = Math.min(4, Math.max(2, Math.ceil(normalized.length / 66)))
  const targetLength = Math.ceil(normalized.length / desiredCount)
  const beats: string[] = []
  let current = ''
  clauses.forEach((clause, index) => {
    const remainingClauses = clauses.length - index
    const remainingSlots = desiredCount - beats.length
    if (current && current.length + clause.length > targetLength && remainingClauses >= remainingSlots) {
      beats.push(current)
      current = clause
    } else {
      current += clause
    }
  })
  if (current) beats.push(current)
  if (beats.length <= 4) return beats
  return [...beats.slice(0, 3), beats.slice(3).join('')]
}

function useTypewriter(beats: string[], presentationKey: string, paused = false) {
  const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const signature = beats.join('\u241e')
  const firstBeat = beats[0] || ''
  const firstFrameLength = reducedMotion && firstBeat ? 1 : 0
  const [state, setState] = useState({ key: presentationKey, beatIndex: 0, visibleLength: firstFrameLength, readyForChoices: false })
  useEffect(() => {
    // Even with reduced motion, do not reveal a new scene in full on its first
    // paint. One deliberate tap reveals the whole passage; the following tap
    // alone unlocks choices. This keeps the authored reading beat deterministic.
    setState({ key: presentationKey, beatIndex: 0, visibleLength: reducedMotion && firstBeat ? 1 : 0, readyForChoices: false })
  }, [firstBeat, presentationKey, reducedMotion, signature])
  const isCurrent = state.key === presentationKey
  const beatIndex = isCurrent ? Math.min(state.beatIndex, Math.max(0, beats.length - 1)) : 0
  const currentBeat = beats[beatIndex] || ''
  useEffect(() => {
    if (paused || reducedMotion || !currentBeat || !isCurrent) return
    const timer = window.setInterval(() => {
      setState(current => {
        if (current.key !== presentationKey || current.beatIndex !== beatIndex || current.visibleLength >= currentBeat.length) {
          window.clearInterval(timer)
          return current
        }
        return { ...current, visibleLength: Math.min(currentBeat.length, current.visibleLength + 1) }
      })
    }, 52)
    return () => window.clearInterval(timer)
  }, [beatIndex, currentBeat, isCurrent, paused, presentationKey, reducedMotion])
  const visibleLength = isCurrent ? state.visibleLength : 0
  const readyForChoices = isCurrent && state.readyForChoices
  const complete = visibleLength >= currentBeat.length
  const isLastBeat = beatIndex >= beats.length - 1
  const reveal = () => {
    if (paused) return
    setState(current => {
      if (current.key !== presentationKey) return { key: presentationKey, beatIndex: 0, visibleLength: firstBeat.length, readyForChoices: false }
      const activeBeat = beats[current.beatIndex] || ''
      if (current.visibleLength < activeBeat.length) return { ...current, visibleLength: activeBeat.length, readyForChoices: false }
      if (current.beatIndex < beats.length - 1) {
        const nextBeatIndex = current.beatIndex + 1
        const nextBeat = beats[nextBeatIndex] || ''
        return { ...current, beatIndex: nextBeatIndex, visibleLength: reducedMotion && nextBeat ? 1 : 0, readyForChoices: false }
      }
      return { ...current, readyForChoices: true }
    })
  }
  return { text: currentBeat.slice(0, visibleLength), complete, readyForChoices, reveal, beatIndex, beatCount: beats.length, isLastBeat }
}

type StoryOverlayPhase = 'narration' | 'narration-exit' | 'interaction'

function useStoryOverlayPhase(readyForChoices: boolean, presentationKey: string): StoryOverlayPhase {
  const [state, setState] = useState<{ key: string; phase: StoryOverlayPhase }>({ key: presentationKey, phase: 'narration' })
  const phase = state.key === presentationKey ? state.phase : 'narration'
  useEffect(() => {
    setState({ key: presentationKey, phase: 'narration' })
  }, [presentationKey])
  useEffect(() => {
    if (!readyForChoices) return
    setState(current => current.key === presentationKey
      ? { ...current, phase: 'narration-exit' }
      : { key: presentationKey, phase: 'narration' })
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const timer = window.setTimeout(() => {
      setState(current => current.key === presentationKey
        ? { ...current, phase: 'interaction' }
        : current)
    }, reducedMotion ? 20 : 280)
    return () => window.clearTimeout(timer)
  }, [presentationKey, readyForChoices])
  return phase
}

type AudioOwner = { video: HTMLVideoElement; mute: () => void }
let activeAudioOwner: AudioOwner | null = null
let audioIntentUnlocked = false

function unlockAudioIntent() {
  audioIntentUnlocked = true
}

function claimAudioOwner(video: HTMLVideoElement, mute: () => void) {
  if (activeAudioOwner?.video !== video) activeAudioOwner?.mute()
  activeAudioOwner = { video, mute }
}

function releaseAudioOwner(video: HTMLVideoElement) {
  if (activeAudioOwner?.video === video) activeAudioOwner = null
}

function useEventPlayback(videoRef: React.RefObject<HTMLVideoElement>, src: string, active: boolean, firstPassConsumed = false) {
  const [phase, setPhase] = useState<'first' | 'loop'>(firstPassConsumed ? 'loop' : 'first')
  const [muted, setMuted] = useState(firstPassConsumed || !audioIntentUnlocked)
  const [needsGesture, setNeedsGesture] = useState(!firstPassConsumed && !audioIntentUnlocked)
  const mutedRef = useRef(muted)
  const phaseRef = useRef(phase)
  mutedRef.current = muted
  phaseRef.current = phase

  const muteFromCoordinator = () => {
    const video = videoRef.current
    if (video) video.muted = true
    mutedRef.current = true
    setMuted(true)
  }

  useEffect(() => {
    const nextPhase = firstPassConsumed ? 'loop' : 'first'
    const nextMuted = firstPassConsumed || !audioIntentUnlocked
    phaseRef.current = nextPhase
    mutedRef.current = nextMuted
    setPhase(nextPhase)
    setMuted(nextMuted)
    setNeedsGesture(!firstPassConsumed && !audioIntentUnlocked)
    const video = videoRef.current
    if (video) {
      video.pause()
      video.currentTime = 0
      video.muted = nextMuted
    }
  }, [firstPassConsumed, src, videoRef])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    let cancelled = false
    const play = () => {
      if (!active || document.hidden) {
        video.pause()
        releaseAudioOwner(video)
        return
      }
      video.muted = mutedRef.current
      if (!video.muted) claimAudioOwner(video, muteFromCoordinator)
      void video.play().catch(() => {
        if (cancelled || video.muted) return
        // Browsers may reject unmuted autoplay even after an earlier entry
        // gesture. Fall back to motion immediately and surface an explicit,
        // one-tap sound affordance instead of failing playback altogether.
        video.muted = true
        mutedRef.current = true
        setMuted(true)
        setNeedsGesture(true)
        releaseAudioOwner(video)
        void video.play().catch(() => undefined)
      })
    }
    play()
    document.addEventListener('visibilitychange', play)
    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', play)
      video.pause()
      releaseAudioOwner(video)
    }
  }, [active, muted, src, videoRef])

  const toggleSound = () => {
    unlockAudioIntent()
    const video = videoRef.current
    const nextMuted = !mutedRef.current
    mutedRef.current = nextMuted
    setMuted(nextMuted)
    setNeedsGesture(false)
    if (!video) return
    video.muted = nextMuted
    if (nextMuted) {
      releaseAudioOwner(video)
      return
    }
    claimAudioOwner(video, muteFromCoordinator)
    void video.play().catch(() => {
      video.muted = true
      mutedRef.current = true
      setMuted(true)
      setNeedsGesture(true)
      releaseAudioOwner(video)
    })
  }

  const handleEnded = () => {
    const video = videoRef.current
    if (!video) return
    const isFirstPass = phaseRef.current === 'first'
    const nextMuted = isFirstPass ? true : mutedRef.current
    if (isFirstPass) {
      phaseRef.current = 'loop'
      setPhase('loop')
      mutedRef.current = true
      setMuted(true)
      setNeedsGesture(false)
    }
    video.currentTime = 0
    video.muted = nextMuted
    if (nextMuted) releaseAudioOwner(video)
    else claimAudioOwner(video, muteFromCoordinator)
    if (active && !document.hidden) void video.play().catch(() => undefined)
  }

  return {
    muted,
    phase,
    needsGesture,
    toggleSound,
    handleEnded,
    soundLabel: needsGesture ? '点此开启声音' : muted ? (phase === 'loop' ? '循环已静音' : '声音已关闭') : '声音已开启',
  }
}

function MediaVideo({ src, className = '', poster, onError, onCanPlay, active = true, preload }: {
  src: string; className?: string; poster?: string; onError?: () => void; onCanPlay?: () => void; active?: boolean; preload?: 'none' | 'metadata' | 'auto'
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const syncPlayback = () => {
      if (!active || document.hidden) video.pause()
      else void video.play().catch(() => undefined)
    }
    syncPlayback()
    document.addEventListener('visibilitychange', syncPlayback)
    return () => document.removeEventListener('visibilitychange', syncPlayback)
  }, [active, src])
  return <video ref={videoRef} className={className} src={src} poster={poster} autoPlay={active} muted loop playsInline preload={preload || (active ? 'metadata' : 'none')} onCanPlay={onCanPlay} onError={onError} />
}

function EventMediaVideo({ src, className = '', poster, onError, onCanPlay, onTimeUpdate, active, preload, firstPassConsumed = false }: {
  src: string; className?: string; poster?: string; onError?: () => void; onCanPlay?: () => void
  onTimeUpdate?: (currentTime: number) => void; active: boolean; preload?: 'none' | 'metadata' | 'auto'; firstPassConsumed?: boolean
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const playback = useEventPlayback(videoRef, src, active, firstPassConsumed)
  return <>
    <video ref={videoRef} className={className} src={src} poster={poster} autoPlay={active} muted={playback.muted} playsInline preload={preload || (active ? 'auto' : 'metadata')} onCanPlay={onCanPlay} onError={onError} onTimeUpdate={event => onTimeUpdate?.(event.currentTarget.currentTime)} onEnded={playback.handleEnded} />
    {active && <button type="button" className={`scene-audio-toggle ${playback.needsGesture ? 'scene-audio-toggle--attention' : ''}`} onClick={playback.toggleSound} aria-label={playback.muted ? '开启视频声音' : '关闭视频声音'} aria-pressed={!playback.muted}>
      <span aria-hidden="true"><Icon name={playback.muted ? 'volume-off' : 'volume-on'} tone="rose" /></span><b>{playback.soundLabel}</b>
    </button>}
  </>
}

function SceneMedia({ src, poster, fallbackSrc, fallbackPoster, active, cue, assetId, firstPassConsumed = false, soundEnabled = true, onTimeUpdate }: {
  src: string; poster?: string; fallbackSrc?: string; fallbackPoster?: string
  active: boolean; cue?: string; assetId?: string; firstPassConsumed?: boolean; soundEnabled?: boolean; onTimeUpdate?: (currentTime: number) => void
}) {
  const [layers, setLayers] = useState<Array<{ src: string; poster?: string }>>(() => src ? [{ src, poster }] : [])
  const [visibleSrc, setVisibleSrc] = useState(src)
  const desiredSrcRef = useRef(src)
  const fallbackRef = useRef({ src: fallbackSrc, poster: fallbackPoster })
  const promotionRef = useRef('')
  const promotionTimerRef = useRef<number | null>(null)
  useEffect(() => {
    desiredSrcRef.current = src
    fallbackRef.current = { src: fallbackSrc, poster: fallbackPoster }
    promotionRef.current = ''
    if (promotionTimerRef.current) window.clearTimeout(promotionTimerRef.current)
    if (!src) {
      setVisibleSrc('')
      setLayers([])
      return () => {
        if (promotionTimerRef.current) window.clearTimeout(promotionTimerRef.current)
      }
    }
    setLayers(current => {
      const desired = { src, poster }
      const existing = current.find(layer => layer.src === src)
      if (existing) return current.map(layer => layer.src === src ? desired : layer).slice(-2)
      return [...current.slice(-1), desired]
    })
    return () => {
      if (promotionTimerRef.current) window.clearTimeout(promotionTimerRef.current)
    }
  }, [fallbackPoster, fallbackSrc, poster, src])
  const promote = (readySrc: string) => {
    if (readySrc !== desiredSrcRef.current || promotionRef.current === readySrc) return
    promotionRef.current = readySrc
    setVisibleSrc(readySrc)
    promotionTimerRef.current = window.setTimeout(() => {
      setLayers(current => current.filter(layer => layer.src === readySrc))
      promotionTimerRef.current = null
    }, 420)
  }
  const reject = (failedSrc: string) => {
    if (failedSrc !== desiredSrcRef.current) return
    const fallback = fallbackRef.current
    if (fallback.src && fallback.src !== failedSrc) {
      desiredSrcRef.current = fallback.src
      promotionRef.current = ''
      setLayers(current => {
        const retained = current.filter(layer => layer.src !== failedSrc && layer.src !== fallback.src)
        return [...retained.slice(-1), { src: fallback.src as string, poster: fallback.poster }]
      })
      return
    }
    // Do not leave either a failed video element or the previous scene playing
    // behind the new protagonist poster. A missing variant is a deliberate
    // static fallback, never permission to borrow another character's footage.
    setVisibleSrc('')
    setLayers([])
  }
  return <div className="scene-media" data-media-cue={cue || undefined} data-media-asset-id={assetId || undefined} role={cue ? 'img' : undefined} aria-label={cue ? `剧情动态画面：${cue}` : undefined}>
    {poster && <img className="scene-media__poster" src={poster} alt="" aria-hidden="true" />}
    {layers.map(layer => soundEnabled ? <EventMediaVideo
        key={layer.src}
        className={`scene-media__layer ${visibleSrc === layer.src ? 'scene-media__layer--visible' : ''}`}
        src={layer.src}
        poster={layer.poster}
        active={active && visibleSrc === layer.src}
        firstPassConsumed={firstPassConsumed && visibleSrc === layer.src}
        onTimeUpdate={active && visibleSrc === layer.src ? onTimeUpdate : undefined}
        preload={desiredSrcRef.current === layer.src ? 'auto' : 'metadata'}
        onCanPlay={() => promote(layer.src)}
        onError={() => reject(layer.src)}
      /> : <MediaVideo
        key={layer.src}
        className={`scene-media__layer ${visibleSrc === layer.src ? 'scene-media__layer--visible' : ''}`}
        src={layer.src}
        poster={layer.poster}
        active={active && visibleSrc === layer.src}
        preload={desiredSrcRef.current === layer.src ? 'auto' : 'metadata'}
        onCanPlay={() => promote(layer.src)}
        onError={() => reject(layer.src)}
      />)}
  </div>
}

function HeartMark({ small = false }: { small?: boolean }) {
  return <span className={small ? 'heart-mark heart-mark--small' : 'heart-mark'} aria-hidden="true"><Icon name="heart" tone="rose" size={small ? 24 : 64} /></span>
}

function CharacterIdentityPlate({ identity, context = '嘉宾登场', className = '', durationSeconds = 3.4 }: { identity: SceneIdentityCard; context?: string; className?: string; durationSeconds?: number }) {
  const age = identity.age ? `${identity.age}岁 · ` : ''
  return <div className={`scene-identity-plate ${className}`} style={{ '--accent': identity.accent || '#d986a3', '--identity-duration': `${Math.max(.8, durationSeconds)}s` } as React.CSSProperties} aria-label={`${identity.name}，${publicOccupation(identity)}，${identity.mbti}，${identity.tagline || ''}`}>
    <span>{context}</span>
    <b>{identity.name}</b>
    <small>{age}{publicOccupation(identity)} · {identity.mbti}</small>
    {identity.tagline && <em>{identity.tagline}</em>}
  </div>
}

function SceneIdentitySequence({ cards, sceneKey, timeline = [], currentTime = 0, context = '嘉宾登场', className = '' }: { cards: SceneIdentityCard[]; sceneKey: string; timeline?: SceneIdentityTimeline[]; currentTime?: number; context?: string; className?: string }) {
  const [timelineCycleDone, setTimelineCycleDone] = useState(false)
  const lastTimelineTimeRef = useRef(0)
  const signature = cards.map(card => identityId(card) || `${card.name}:${card.mbti}`).join('|')
  const timelineSignature = timeline.map(item => `${item.characterId}:${item.startSeconds}:${item.endSeconds}`).join('|')
  useEffect(() => {
    setTimelineCycleDone(false)
    lastTimelineTimeRef.current = 0
  }, [sceneKey, signature, timelineSignature])
  const timelineWrappedThisFrame = timeline.length > 0 && currentTime + .2 < lastTimelineTimeRef.current
  useEffect(() => {
    if (!timeline.length) return
    if (currentTime + .2 < lastTimelineTimeRef.current) setTimelineCycleDone(true)
    lastTimelineTimeRef.current = currentTime
  }, [currentTime, timeline.length, timelineSignature])
  const timedEntry = timeline.find(item => currentTime >= item.startSeconds && currentTime < item.endSeconds)
  const identity = timeline.length
    ? (!timelineCycleDone && !timelineWrappedThisFrame && timedEntry ? cards.find(card => identityId(card) === timedEntry.characterId) : undefined)
    : cards[0]
  if (!identity) return null
  const identityKey = timedEntry ? `${timedEntry.characterId}:${timedEntry.startSeconds}` : `${identityId(identity) || identity.name}:lead`
  const durationSeconds = timedEntry ? timedEntry.endSeconds - timedEntry.startSeconds : 3.4
  return <CharacterIdentityPlate key={`${sceneKey}:${identityKey}`} identity={identity} context={context} className={className} durationSeconds={durationSeconds} />
}

function Loading() {
  return <main className="loading-screen"><div className="loading-orbit"><HeartMark /></div><p>正在接入心动小屋…</p></main>
}

function LoginGate({ message }: { message: string }) {
  return (
    <main className="login-gate">
      <div className="login-card glass-card">
        <span className="kicker">HEART JOURNEY · INTERNAL PREVIEW</span>
        <HeartMark />
        <h1>需要内网身份</h1>
        <p>{message}</p>
        <button className="primary-button" onClick={() => location.reload()}>重新进入</button>
      </div>
    </main>
  )
}

const MBTI_ORDER = ['INTJ', 'ISFJ', 'ESTP', 'INTP', 'INFJ', 'ENFP', 'ESFJ', 'ISTP']

const STARTUP_STAGE_LABELS = [
  '正在创建你的本局…',
  '正在安排同住嘉宾…',
  '正在准备第一幕…',
  '连接比平时稍慢，仍在为你开启…',
]

function Landing({ characters, onStart, busy, startError }: { characters: Character[]; onStart: (mbti: string, perspectiveCharacterId: string) => void; busy: boolean; startError?: string }) {
  const [phase, setPhase] = useState<'intro' | 'mbti' | 'role'>('intro')
  const [selectedMbti, setSelectedMbti] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [startupStage, setStartupStage] = useState(0)
  const availableMbtis = useMemo(() => {
    const values = new Set(characters.map(character => character.mbti).filter(Boolean))
    return [...values].sort((left, right) => {
      const leftIndex = MBTI_ORDER.indexOf(left)
      const rightIndex = MBTI_ORDER.indexOf(right)
      if (leftIndex < 0 || rightIndex < 0) return left.localeCompare(right)
      return leftIndex - rightIndex
    })
  }, [characters])
  const roleOptions = useMemo(() => characters.filter(character => character.mbti === selectedMbti), [characters, selectedMbti])
  const selected = roleOptions.find(character => character.id === selectedId)
  const backgroundVideo = phase === 'role' && selected ? (selected.video || '').trim() : '/media/video/E01-arrival-reveal.mp4'
  const backgroundPoster = phase === 'role' && selected ? selected.portrait : undefined
  const chooseMbti = (mbti: string) => {
    setSelectedMbti(mbti)
    setSelectedId('')
    setPhase('role')
  }
  useEffect(() => {
    if (!busy) {
      setStartupStage(0)
      return
    }
    setStartupStage(0)
    const timers = [
      window.setTimeout(() => setStartupStage(1), 900),
      window.setTimeout(() => setStartupStage(2), 2800),
      window.setTimeout(() => setStartupStage(3), 6500),
    ]
    return () => timers.forEach(timer => window.clearTimeout(timer))
  }, [busy])
  return (
    <main className={`landing landing--${phase}`}>
      <div className="landing-media" aria-hidden="true">
        {busy && backgroundPoster
          ? <div className="scene-media scene-media--startup-poster"><img className="scene-media__poster" src={backgroundPoster} alt="" /></div>
          : <SceneMedia src={backgroundVideo} poster={backgroundPoster} active soundEnabled={false} />}
        <div className="landing-scrim" />
        <div className="sun-glow" />
      </div>
      <header className="landing-topbar">
        <span>MBTI 沉浸式恋爱观察实验</span>
        <span className="live-pill"><i /> DAY 1</span>
      </header>
      {phase === 'intro' ? <>
        <section className="landing-copy landing-copy--intro">
          <p className="landing-overline">7 天 6 夜 · 海岛心动酒店</p>
          <div className="title-lockup"><h1>心动之旅</h1><HeartMark /><p>MBTI 恋爱观察实验</p></div>
        </section>
        <section className="show-premise glass-card">
          <span>欢迎入住</span>
          <h2>七天六夜，故事从第一声“你好”开始。</h2>
          <p>欢迎来到《心动之旅》。八位来自不同生活轨迹的嘉宾，将在海岛酒店一起生活七天六夜。从初次见面、一起做饭，到组队约会和每晚的心动短信，共同生活的衣食住行会碰撞出怎样的火花？让我们一起期待。</p>
          <blockquote>帮助别人，也照见自己。找到一位愿意同行的人，更好地发现自己、爱自己。</blockquote>
          <button className="primary-button start-button" onClick={() => { unlockAudioIntent(); setPhase('mbti') }}><span>先选择你的 MBTI</span><i><Icon name="arrow-right" /></i></button>
        </section>
      </> : phase === 'mbti' ? <>
        <section className="landing-copy landing-copy--selection">
          <p className="landing-overline">STEP 1 · 选择人格</p>
          <h1 className="selection-title">你想以哪种方式，走进这七天？</h1>
          <p className="selection-subtitle">先选择 MBTI，再从对应的一男一女两位角色中确定你的观察视角。</p>
        </section>
        <section className="mbti-step glass-card" aria-label="选择 MBTI">
          <div className="selection-step-heading"><span>本季开放 8 种人格</span><small>每种都有男性与女性角色</small></div>
          <div className="mbti-grid">
            {availableMbtis.map(mbti => {
              const mbtiCharacters = characters.filter(character => character.mbti === mbti)
              const previewCharacters = [...mbtiCharacters]
                .sort((left, right) => {
                  const genderRank = (character: Character) => character.gender === '男性' ? 0 : character.gender === '女性' ? 1 : 2
                  return genderRank(left) - genderRank(right)
                })
                .slice(0, 2)
              const roleSummary = previewCharacters.map(character => `${character.gender || '嘉宾'}${character.name}`).join('、')
              return <button key={mbti} onClick={() => chooseMbti(mbti)} aria-label={`选择 ${mbti}，${roleSummary || `有 ${mbtiCharacters.length} 位角色`}`}>
                <span className="mbti-card__copy">
                  <b>{mbti}</b>
                  <span className="mbti-card__meta">{mbtiCharacters.length >= 2 ? '一男一女 · 2 位角色' : `${mbtiCharacters.length} 位角色`}</span>
                </span>
                <span className="mbti-card__faces">
                  {previewCharacters.map(character => <img
                    key={character.id}
                    src={character.portrait}
                    alt={`${mbti} ${character.gender || '嘉宾'}角色${character.name}`}
                    title={`${character.name} · ${character.gender || '嘉宾'}`}
                    loading="lazy"
                    decoding="async"
                  />)}
                </span>
                <i aria-hidden="true"><Icon name="arrow-right" size={16} tone="rose" /></i>
              </button>
            })}
          </div>
          <button className="selection-back" onClick={() => setPhase('intro')}><Icon name="arrow-left" size={15} />返回节目介绍</button>
        </section>
      </> : <>
        <section className="landing-copy landing-copy--role">
          <p className="landing-overline">STEP 2 · 选择角色</p>
          <h1 className="selection-title">{selectedMbti} 的两个故事起点</h1>
          <p className="selection-subtitle">选择性别与具体人物。另一位同类型嘉宾仍可能进入本局，成为你可以认识的人。</p>
        </section>
        <section className="role-step" aria-label={`选择 ${selectedMbti} 角色`}>
          <div className="role-picker">
            {roleOptions.map(character => <button key={character.id} className={character.id === selected?.id ? 'active' : ''} disabled={busy} onClick={() => setSelectedId(character.id)} style={{ '--accent': character.accent } as React.CSSProperties} aria-pressed={character.id === selected?.id} aria-label={`选择${character.gender || ''}角色${character.name}，${publicOccupation(character)}，${character.tagline}`}>
              <img src={character.portrait} alt={`${character.name}头像`} />
              <span><em>{character.gender || '嘉宾'}</em><b>{character.name}</b><small>{publicOccupation(character)}</small><small>{character.tagline}</small></span><i><Icon name="arrow-right" size={17} tone="rose" /></i>
            </button>)}
          </div>
          {selected ? <section className="character-preview glass-card" style={{ '--accent': selected.accent } as React.CSSProperties}>
            <div className="character-preview__heading"><span>{selected.mbti} · {selected.gender || '嘉宾'}</span><small>你的视角 · 开局后不可与自己私聊</small></div>
            <h2>{selected.publicMask}</h2>
            <p>{selected.independentInterest}</p>
            <dl><div><dt>表达方式</dt><dd>{selected.voice}</dd></div><div><dt>关系边界</dt><dd>{selected.boundary}</dd></div></dl>
            {selected.mediaStatus === 'planned' && <p className="static-media-note">当前以静态人物图进入；动态形象准备完成后会自动启用，不会借用其他嘉宾的视频。</p>}
            <button className="primary-button start-button" disabled={busy} onClick={() => { unlockAudioIntent(); onStart(selected.mbti, selected.id) }}><span>{busy ? STARTUP_STAGE_LABELS[startupStage] : startError ? '重新尝试开启' : `跟随${selected.name}进入小屋`}</span><i>{busy ? '···' : <Icon name="arrow-right" />}</i></button>
            {(busy || startError) && <p className={`role-start-feedback ${startError ? 'role-start-feedback--error' : ''}`} role={startError ? 'alert' : 'status'} aria-live="polite">
              {startError || (startupStage < 3 ? '正在建立本局，不会等待视频下载，也无需重复点击。' : '人物图片会先陪你等待；动态画面进入剧情后再加载。')}
            </p>}
          </section> : <div className="role-empty glass-card"><span>选择一位角色</span><p>点击上方的男性或女性角色，先读完人物详情，再决定是否以 TA 的视角开局。</p></div>}
          <button className="selection-back" disabled={busy} onClick={() => { setSelectedId(''); setPhase('mbti') }}><Icon name="arrow-left" size={15} />重新选择 MBTI</button>
        </section>
      </>}
    </main>
  )
}

function sceneContext(node: StoryNode, snapshot: Snapshot) {
  const [eyebrowLocation, eyebrowTime] = (node.eyebrow || '').split('/').map(value => value.trim())
  const locationName = snapshot.sceneContext?.locationName || node.location || eyebrowLocation || '心动小屋'
  return {
    locationId: snapshot.sceneContext?.locationId,
    locationName,
    location: locationName,
    time: snapshot.sceneContext?.time || node.time || eyebrowTime || '',
  }
}

function HeartInboxPhone({ snapshot, characters }: { snapshot: Snapshot; characters: Character[] }) {
  const incoming = snapshot.heartMailbox?.received || []
  const sent = snapshot.heartMailbox?.sent || []
  const outgoing = sent[sent.length - 1]
  const recipient = outgoing?.recipientCharacterId ? characters.find(character => character.id === outgoing.recipientCharacterId) : undefined
  return (
    <section className="heart-phone" aria-label="心动短信手机">
      <div className="heart-phone__speaker" aria-hidden="true" />
      <header><span>22:30</span><b>心动短信</b><i>{incoming.length ? `${incoming.length} 条新消息` : '收件结果'}</i></header>
      <div className="heart-phone__screen">
        {incoming.length ? incoming.map((message, index) => (
          <article className="heart-message heart-message--incoming" key={message.id || `${index}-${message.text}`}>
            <span>{message.isAnonymous === false && message.senderCharacterId ? (characters.find(character => character.id === message.senderCharacterId)?.name || '一位嘉宾') : '匿名嘉宾'} 发来{message.receivedAt ? ` · ${new Date(message.receivedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}` : ''}</span>
            <p>{message.text}</p>
          </article>
        )) : <article className="heart-message heart-message--pending">
          <span>你的收件箱</span>
          <p>节目组尚未公布收件结果。收到的真实短信会直接出现在这里。</p>
        </article>}
        {outgoing && <article className="heart-message heart-message--outgoing">
          <span>你发给 {recipient?.name || '今晚想继续认识的人'}</span>
          <p>{outgoing.text}</p>
        </article>}
      </div>
      <footer><span>来自本轮真实收发记录</span><i><Icon name="status-dot" size={13} tone="rose" /></i></footer>
    </section>
  )
}

const HEART_MESSAGE_SUGGESTIONS = [
  '今天和你聊天很舒服，希望明天还能坐近一点。',
  '谢谢你记住我随口说的小事，想继续认识你。',
  '今晚的海风很好，下次一起去露台走走吧。',
]

function HeartMessageComposer({ choices, characters, busy, disabled, onSend }: {
  choices: Choice[]; characters: Character[]; busy: boolean; disabled: boolean
  onSend: (choice: Choice, text: string) => Promise<void>
}) {
  const [selectedId, setSelectedId] = useState(choices[0]?.id || '')
  const [draft, setDraft] = useState(HEART_MESSAGE_SUGGESTIONS[0])
  const selectedChoice = choices.find(choice => choice.id === selectedId) || choices[0]
  const selectedCharacterId = selectedChoice?.characterId || selectedChoice?.targetCharacterId
  const selectedCharacter = characters.find(character => character.id === selectedCharacterId)
  return (
    <section className="heart-compose" aria-label="编辑心动短信">
      <div className="character-choices character-choices--compact" role="list" aria-label="选择收信人">
        {choices.map(choice => {
          const characterId = choice.characterId || choice.targetCharacterId
          const character = characters.find(item => item.id === characterId)
          const selected = choice.id === selectedChoice?.id
          return <button type="button" role="listitem" className={selected ? 'selected' : ''} key={choice.id} onClick={() => setSelectedId(choice.id)} disabled={busy || disabled} style={character ? { '--accent': character.accent } as React.CSSProperties : undefined} aria-pressed={selected}>
            {character && <img src={character.portrait} alt={`${character.name}头像`} />}
            <span><b>{character?.name || choice.label}</b><small>{character ? `${character.mbti} · ${publicOccupation(character)}` : choice.hint}</small></span>
            <i>{selected ? <Icon name="check" size={16} tone="rose" /> : <Icon name="radio-empty" size={16} tone="lavender" />}</i>
          </button>
        })}
      </div>
      {selectedChoice && <div className="heart-compose__phone">
        <header><span>发送给</span><b>{selectedCharacter?.name || '一位嘉宾'}</b><small>匿名发送</small></header>
        <div className="heart-compose__suggestions" aria-label="短信建议">
          {HEART_MESSAGE_SUGGESTIONS.map((suggestion, index) => <button type="button" key={suggestion} onClick={() => setDraft(suggestion)}><i>0{index + 1}</i>{suggestion}</button>)}
        </div>
        <label><span>写下你真正想说的话</span><textarea value={draft} onChange={event => setDraft(event.target.value)} maxLength={120} rows={3} placeholder="也可以完全自己写…" /></label>
        <footer><small>{draft.trim().length}/120 · 你可以继续修改</small><button type="button" disabled={busy || disabled || !draft.trim()} onClick={() => onSend(selectedChoice, draft.trim())}>{busy ? '发送中…' : '发送这条短信'}</button></footer>
      </div>}
    </section>
  )
}

function FreeChoiceComposer({ choices, busy, disabled, onSend }: {
  choices: Choice[]; busy: boolean; disabled: boolean; onSend: (choice: Choice, customText: string) => Promise<void>
}) {
  const [draft, setDraft] = useState('')
  const [routeId, setRouteId] = useState(choices[0]?.id || '')
  const route = choices.find(choice => choice.id === routeId) || choices[0]
  if (!route) return null
  return <section className="free-choice-composer" aria-label="自定义行动">
    <label><span>或者，用你自己的方式表达</span><textarea rows={2} maxLength={180} value={draft} onChange={event => setDraft(event.target.value)} placeholder="例如：先和大家打声招呼，再去看看有没有人需要帮忙…" /></label>
    <div className="free-choice-composer__routes"><span>这句话更接近</span>{choices.map((choice, index) => <button type="button" className={choice.id === route.id ? 'selected' : ''} aria-pressed={choice.id === route.id} key={choice.id} onClick={() => setRouteId(choice.id)}>方案 {String(index + 1).padStart(2, '0')}</button>)}</div>
    <button className="free-choice-composer__send" type="button" disabled={busy || disabled || !draft.trim()} onClick={() => onSend(route, draft.trim())}><span>{busy ? '正在写入故事…' : '用这句话推进剧情'}</span><Icon className={busy ? 'ui-icon--placeholder' : ''} name="arrow-right" size={17} /></button>
    <small>当前剧情仍沿你选中的行动路线推进；自定义原话会一并发送，供后端人物记忆接入。</small>
  </section>
}

function CharacterDock({ characters, snapshot, chatContexts, guidedCharacterId, guidedComplete = false, currentLocation, currentTime, groupDisabled = false, onOpen, onOpenGroup }: {
  characters: Character[]; snapshot: Snapshot; guidedCharacterId?: string | null; guidedComplete?: boolean
  chatContexts?: ChatContexts; currentLocation: string; currentTime?: string; groupDisabled?: boolean
  onOpen: (character: Character, context: ConversationContext) => void
  onOpenGroup: (venue: ChatVenue) => void
}) {
  const guidedRef = useRef<HTMLButtonElement>(null)
  const venues = chatContexts?.venues || []
  const initialVenueId = chatContexts?.scene?.locationId && venues.some(venue => venue.locationId === chatContexts.scene?.locationId)
    ? chatContexts.scene.locationId
    : venues[0]?.locationId || 'all'
  const [locationFilter, setLocationFilter] = useState(initialVenueId)
  const castIdSet = snapshot.castIds?.length === 8 ? new Set(snapshot.castIds) : null
  const runCharacters = castIdSet ? characters.filter(character => castIdSet.has(character.id)) : characters
  const perspectiveCharacter = runCharacters.find(character => character.id === snapshot.player.perspectiveCharacterId) || runCharacters.find(character => character.isPlayerPerspective)
  const presentNpcIds = new Set(venues.flatMap(venue => venue.characters.map(character => character.id)))
  const availableCharacters = runCharacters.filter(character => character.id !== perspectiveCharacter?.id && !character.isPlayerPerspective && (!venues.length || presentNpcIds.has(character.id)))
  const selectedVenue = venues.find(venue => venue.locationId === locationFilter)
  const selectedIds = new Set(selectedVenue?.characters.map(character => character.id) || [])
  const filteredCharacters = locationFilter === 'all' ? availableCharacters : availableCharacters.filter(character => selectedIds.has(character.id))
  const guidedCharacter = availableCharacters.find(character => character.id === guidedCharacterId)
  const dockCharacters = guidedCharacter
    ? [perspectiveCharacter, guidedCharacter, ...filteredCharacters.filter(character => character.id !== guidedCharacter.id)].filter((character, index, values): character is Character => !!character && values.findIndex(item => item?.id === character.id) === index)
    : [perspectiveCharacter, ...filteredCharacters].filter((character): character is Character => !!character)
  useEffect(() => {
    if (guidedCharacter) guidedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [guidedCharacter?.id, snapshot.nodeId])
  useEffect(() => {
    if (!venues.length) return
    if (locationFilter === 'all' || venues.some(venue => venue.locationId === locationFilter)) return
    setLocationFilter(initialVenueId)
  }, [initialVenueId, locationFilter, venues])
  const venueForCharacter = (characterId: string) => venues.find(venue => venue.characters.some(character => character.id === characterId))
  return (
    <nav className={`character-dock ${guidedCharacter ? 'character-dock--guided' : ''} ${venues.length ? 'character-dock--with-location' : ''}`} aria-label="按地点发起嘉宾交流">
      <div className="dock-label">
        <span>{guidedCharacter ? (guidedComplete ? '这次交流已完成' : '该你开口了') : '心动小屋'}</span>
        <small>{guidedCharacter ? (guidedComplete ? `${guidedCharacter.name}已记住这次对话` : `去和${guidedCharacter.name}打个招呼`) : `${currentLocation}${currentTime ? ` · ${currentTime}` : ''}`}</small>
      </div>
      {!!venues.length && <div className="dock-location-filter" aria-label="按真实地点筛选嘉宾">
        <span>嘉宾在哪里</span>
        <select value={locationFilter} onChange={event => setLocationFilter(event.target.value)}>
          <option value="all">全部地点</option>
          {venues.map(venue => <option value={venue.locationId} key={venue.locationId}>{venue.locationName} · {venue.characters.length}人</option>)}
        </select>
        {selectedVenue?.supportsGroup
          ? <button className="dock-group-launch" type="button" disabled={groupDisabled} onClick={() => onOpenGroup(selectedVenue)}>{groupDisabled ? '先完成破冰' : `和${selectedVenue.characters.length}人群聊`}</button>
          : <small>{selectedVenue ? `${selectedVenue.locationName}仅支持私聊` : '选择地点可发起群聊'}</small>}
      </div>}
      <div className="dock-scroll">
        {dockCharacters.map((character) => {
          const memoryCount = snapshot.echoMemories.filter(m => m.characterId === character.id).length
          const guided = character.id === guidedCharacter?.id
          const isSelf = character.id === snapshot.player.perspectiveCharacterId || character.isPlayerPerspective === true
          const chatUnavailable = isSelf || character.chatEnabled === false
          const venue = isSelf ? undefined : venueForCharacter(character.id)
          const context: ConversationContext = {
            time: venue?.time || chatContexts?.scene?.time || currentTime,
            locationId: venue?.locationId || chatContexts?.scene?.locationId,
            locationName: venue?.locationName || chatContexts?.scene?.locationName || currentLocation,
            participantIds: [snapshot.player.perspectiveCharacterId, character.id].filter((value): value is string => !!value),
            channel: '1v1',
          }
          return (
            <button ref={guided ? guidedRef : undefined} className={`dock-avatar ${guided ? 'dock-avatar--guided' : ''} ${chatUnavailable ? 'dock-avatar--unavailable' : ''} ${isSelf ? 'dock-avatar--self' : ''}`} key={character.id} onClick={() => !chatUnavailable && onOpen(character, context)} disabled={chatUnavailable} style={{ '--accent': character.accent } as React.CSSProperties} aria-label={isSelf ? `${character.name}，你的当前视角，不可与自己私聊` : chatUnavailable ? `${character.name}，当前暂不可私聊` : guided ? `剧情正在等你，与${character.name}交流` : `在${venue?.locationName || currentLocation}与${character.name}交流，${character.mbti}，${character.tagline}`}>
              <span className="dock-avatar__photo"><img src={character.portrait} alt="" />{(guided || memoryCount > 0) && <i className={guided ? `guided-badge ${guidedComplete ? 'guided-badge--done' : ''}` : ''}>{guided ? (guidedComplete ? <Icon name="check" size={10} /> : 1) : memoryCount}</i>}</span>
              <span className="dock-avatar__copy"><span><b>{character.name}</b><em>{character.mbti}</em></span><small className="dock-avatar__role">{publicOccupation(character)} · {character.gender || '嘉宾'}</small><small>{isSelf ? '你的视角 · 不可私聊' : chatUnavailable ? '当前剧情中暂不可私聊' : `${venue?.locationName || currentLocation} · ${character.tagline}`}</small></span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}

function ChatSheet({ character, characters, snapshot, embeddedOpener, context, error, onClose, onSend, busy }: {
  character: Character; characters: Character[]; snapshot: Snapshot; embeddedOpener?: ChatOpenerPayload
  context: ConversationContext; error?: string
  onClose: () => void
  onSend: (message: string, context: ConversationContext) => Promise<void>; busy: boolean
}) {
  const [draft, setDraft] = useState('')
  const firstLoadRef = useRef(true)
  const endpointSupportedRef = useRef(true)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const streamRef = useRef<HTMLDivElement>(null)
  const memories = snapshot.echoMemories.filter(memory => memory.characterId === character.id)
  const latest = memories[memories.length - 1]
  const perspective = characters.find(item => item.id === snapshot.player.perspectiveCharacterId) || characters.find(item => item.isPlayerPerspective)
  const baseFallback = FALLBACK_OPENERS[character.id] || {
    stageDirection: `${character.name}给你留出了一个可以慢慢说话的位置。`,
    line: `你好，我是${character.name}。刚才大家都在，还没来得及好好认识你。现在感觉怎么样？`,
  }
  const fallback = latest ? {
    stageDirection: `${character.name}看到你回来，把话题留在了上次停下的地方。`,
    line: `你回来了。上次你说到“${(latest.summary || latest.playerText).slice(0, 32)}”，我还记得。今天想先从哪里聊起？`,
  } : baseFallback
  const initialCardOpener = character.opener || character.openingLine
  const initialPayload = embeddedOpener || snapshot.chatOpeners?.[character.id] || (initialCardOpener ? { opener: initialCardOpener, suggestedPrompts: character.suggestedPrompts } : undefined)
  const [opener, setOpener] = useState(() => normalizeOpener(initialPayload, fallback))
  const [openerVisible, setOpenerVisible] = useState(!!initialPayload)
  const [openerLoading, setOpenerLoading] = useState(!initialPayload)
  const [remotePrompts, setRemotePrompts] = useState<ChatSuggestionInput[]>(() => promptsFromPayload(initialPayload))
  const axes = snapshot.relationships?.[character.id]
  const attitude = snapshot.attitudes?.[character.id] || 'curious'
  const currentLocation = context.locationName || '心动小屋'
  const currentTime = context.time
  useEffect(() => {
    const currentEmbedded = embeddedOpener || snapshot.chatOpeners?.[character.id]
    if (currentEmbedded) {
      if (firstLoadRef.current) {
        setOpener(normalizeOpener(currentEmbedded, fallback))
        setOpenerVisible(true)
      }
      setRemotePrompts(promptsFromPayload(currentEmbedded))
      setOpenerLoading(false)
      firstLoadRef.current = false
      return
    }
    if (!endpointSupportedRef.current) {
      setOpener(fallback); setOpenerVisible(true); setOpenerLoading(false); firstLoadRef.current = false
      return
    }
    let cancelled = false
    const initialLoad = firstLoadRef.current
    const grace = initialLoad ? window.setTimeout(() => {
      if (!cancelled) { setOpener(fallback); setOpenerVisible(true) }
    }, 650) : undefined
    if (initialLoad) setOpenerLoading(true)
    api<ChatOpenerPayload>(`/api/runs/${snapshot.runId}/agents/${character.id}/opener?revision=${snapshot.revision}`)
      .then(payload => {
        if (cancelled) return
        if (initialLoad) { setOpener(normalizeOpener(payload, fallback)); setOpenerVisible(true) }
        const generatedPrompts = promptsFromPayload(payload)
        if (generatedPrompts.length) setRemotePrompts(generatedPrompts)
      })
      .catch(() => {
        if (cancelled) return
        endpointSupportedRef.current = false
        if (initialLoad) { setOpener(fallback); setOpenerVisible(true) }
      })
      .finally(() => {
        if (cancelled) return
        if (grace) window.clearTimeout(grace)
        setOpenerLoading(false); firstLoadRef.current = false
      })
    return () => { cancelled = true; if (grace) window.clearTimeout(grace) }
  }, [character.id, embeddedOpener, snapshot.chatOpeners, snapshot.revision, snapshot.runId])
  const firstGreeting: SuggestedPrompt = { text: `你好，我是${perspective?.name || '新来的嘉宾'}。刚才人多，没来得及好好认识你。`, kind: 'followup', label: '先打招呼' }
  const fallbackSuggestions = fallbackPrompts(character, perspective, memories, snapshot.storyArc.phase, snapshot.nodeId)
  const latestSuggestions = latest?.suggestions || latest?.suggestedPrompts || []
  const suggestedPrompts = selectSuggestedPrompts(
    [...latestSuggestions, ...remotePrompts, ...fallbackSuggestions],
    perspective,
    memories.length ? undefined : firstGreeting,
  )
  useEffect(() => {
    // Keep the independent history viewport pinned to the newest turn after
    // the opener resolves, the player sends, or the Agent reply arrives.
    const scrollToEnd = () => {
      const stream = streamRef.current
      if (!stream) return
      stream.scrollTo({ top: stream.scrollHeight, behavior: 'smooth' })
    }
    const frame = window.requestAnimationFrame(scrollToEnd)
    const settle = window.setTimeout(scrollToEnd, 160)
    return () => { window.cancelAnimationFrame(frame); window.clearTimeout(settle) }
  }, [busy, character.id, latest?.id, memories.length, openerLoading, openerVisible])
  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    const message = draft.trim()
    if (!message || busy) return
    setDraft('')
    await onSend(message, context)
  }
  return (
    <div className="sheet-backdrop" role="dialog" aria-modal="true" aria-label={`与${character.name}私聊`}>
      <section className={`chat-sheet ${memories.length || busy ? 'chat-sheet--has-history' : ''}`} style={{ '--accent': character.accent } as React.CSSProperties}>
        <div className="chat-portrait">
          <div className="chat-portrait__media">
            <img className="chat-portrait__blur" src={character.portrait} alt="" />
            {(character.video || '').trim()
              ? <EventMediaVideo className="chat-portrait__subject" src={character.video} poster={character.portrait} active firstPassConsumed />
              : <img className="chat-portrait__subject chat-portrait__subject--static" src={character.portrait} alt={`${character.name}静态人物形象`} />}
          </div>
          <div className="chat-portrait__scrim" />
          <button className="close-button" onClick={onClose} aria-label="关闭私聊"><Icon name="close" size={24} /></button>
          <div className="chat-identity"><span>{character.mbti}</span><h2>{character.name}</h2><p>{publicOccupation(character)} · {character.tagline}</p><small>{currentLocation}{currentTime ? ` · ${currentTime}` : ''}</small></div>
          <div className="memory-seal"><HeartMark small /><span>{memories.length ? `${memories.length} 段共同记忆` : '从这一句话开始记住你'}</span></div>
        </div>
        <div className="chat-body">
          <div className="agent-note">
            <span>当前态度 · {ATTITUDE_LABELS[attitude] || attitude}</span>
            <p>{character.independentInterest}</p>
            {axes && <div className="relationship-axes">
              {(['trust', 'affection', 'respect', 'attraction'] as const).map(axis => <i key={axis}>{AXIS_LABELS[axis]} {axes[axis] >= 0 ? '+' : ''}{axes[axis]}</i>)}
            </div>}
          </div>
          <div className="message-stream" ref={streamRef} role="log" aria-live="polite" aria-label={`与${character.name}的对话记录`} tabIndex={0}>
            {!openerVisible && <div className="message agent opener-loading" aria-live="polite"><b>{character.name}正在朝你走来</b><span><i /><i /><i /></span><small>正在结合此刻的剧情和你们的记忆…</small></div>}
            {openerVisible && <div className="message agent conversation-opener"><b>{character.name} · {latest ? '又见面了' : '初次寒暄'}</b><em>{opener.stageDirection}</em><p>{opener.line}</p>{openerLoading && <small>正在读取此刻更贴近人物卡的表达…</small>}</div>}
            {memories.slice(-10).map(memory => (
              <div className="message-pair" key={memory.id}>
                <div className="message player"><p>{memory.playerText}</p></div>
                <div className="message agent"><b>{character.name} · {ATTITUDE_LABELS[memory.attitude] || memory.attitude}</b>{memory.stageDirection && <em>{memory.stageDirection}</em>}<p>{memory.agentReply}</p><small>{memory.locationName || memory.time ? `${memory.locationName || currentLocation}${memory.time ? ` · ${memory.time}` : ''}｜` : ''}{memory.summary || '已写入你们的共同记忆'}</small></div>
              </div>
            ))}
            {busy && <div className="message agent typing"><i /><i /><i /></div>}
            <div className="message-stream__end" aria-hidden="true" />
          </div>
          <div className="quick-prompts" aria-label="对话建议">
            {suggestedPrompts.map((prompt, index) => <button className={`quick-prompt quick-prompt--${prompt.kind}`} key={`${index}-${prompt.kind}-${prompt.text}`} onClick={() => { setDraft(prompt.text); inputRef.current?.focus() }} aria-label={`${prompt.label}：${prompt.text}`}><i>{prompt.label}</i>{prompt.text}</button>)}
          </div>
          {error && <p className="chat-error" role="alert">{error}</p>}
          <form className="chat-composer" onSubmit={submit}>
            <textarea ref={inputRef} value={draft} maxLength={240} rows={1} placeholder={`只对${character.name}说…`} onChange={e => setDraft(e.target.value)} />
            <button type="submit" disabled={!draft.trim() || busy} aria-label="发送"><Icon name="arrow-up-right" size={22} /></button>
          </form>
          <p className="memory-rule">这段交流只进入 {character.name} 的记忆；边界与剧情事实由游戏规则裁决</p>
        </div>
      </section>
    </div>
  )
}

function createConversationId() {
  return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `group-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function GroupChatSheet({ venue, characters, snapshot, busy, error, onClose, onSend }: {
  venue: ChatVenue; characters: Character[]; snapshot: Snapshot; busy: boolean; error?: string
  onClose: () => void
  onSend: (message: string, participantIds: string[], context: ConversationContext) => Promise<void>
}) {
  const perspectiveId = snapshot.player.perspectiveCharacterId
  const availableIds = venue.characters.map(character => character.id).filter(id => id !== perspectiveId)
  const [selectedIds, setSelectedIds] = useState(() => availableIds.slice(0, Math.min(3, availableIds.length)))
  const [conversationId, setConversationId] = useState(createConversationId)
  const [draft, setDraft] = useState('')
  const streamRef = useRef<HTMLDivElement>(null)
  const selectedCharacters = selectedIds.map(id => characters.find(character => character.id === id)).filter((character): character is Character => !!character)
  const venueMemories = snapshot.echoMemories.filter(memory => memory.channel === 'group' && memory.locationId === venue.locationId)
  const visibleMemories = venueMemories.slice(-18)
  const toggleParticipant = (characterId: string) => {
    setSelectedIds(current => {
      const selected = current.includes(characterId)
      if (selected && current.length <= 2) return current
      if (!selected && current.length >= 4) return current
      const next = selected ? current.filter(id => id !== characterId) : [...current, characterId]
      setConversationId(createConversationId())
      return next
    })
  }
  useEffect(() => {
    const stream = streamRef.current
    if (!stream) return
    const frame = window.requestAnimationFrame(() => stream.scrollTo({ top: stream.scrollHeight, behavior: 'smooth' }))
    return () => window.cancelAnimationFrame(frame)
  }, [busy, visibleMemories.length])
  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    const message = draft.trim()
    if (!message || busy || selectedIds.length < 2) return
    setDraft('')
    const participantIds = [perspectiveId, ...selectedIds].filter((value): value is string => !!value)
    await onSend(message, selectedIds, {
      conversationId,
      time: venue.time || snapshot.sceneContext?.time,
      locationId: venue.locationId,
      locationName: venue.locationName,
      participantIds,
      channel: 'group',
    })
  }
  const promptOptions = [
    `我们都在${venue.locationName}，要不要先说说刚才各自注意到谁了？`,
    '如果明天要三个人组队，你们最想一起做什么？',
    '先不聊任务了，你们来这里最想被别人看见哪一面？',
  ]
  return <div className="sheet-backdrop" role="dialog" aria-modal="true" aria-label={`${venue.locationName}群聊`}>
    <section className="group-chat-sheet">
      <div className="group-chat__backdrop" aria-hidden="true">
        {selectedCharacters.slice(0, 3).map((character, index) => <img src={character.portrait} alt="" key={character.id} style={{ '--portrait-index': index } as React.CSSProperties} />)}
      </div>
      <div className="group-chat__scrim" />
      <header className="group-chat__header">
        <div><span>{venue.locationName} · {venue.time || snapshot.sceneContext?.time || '此刻'}</span><h2>和在场的人聊一会儿</h2><p>选择 2–4 位嘉宾；每个人都会依据自己的角色卡回应，并分别记住这次对话。</p></div>
        <button type="button" onClick={onClose} aria-label="关闭群聊"><Icon name="close" size={24} /></button>
      </header>
      <div className="group-chat__participants" aria-label="选择群聊嘉宾">
        {venue.characters.map(item => {
          const character = characters.find(candidate => candidate.id === item.id)
          const selected = selectedIds.includes(item.id)
          const unavailable = !selected && selectedIds.length >= 4
          return <button type="button" key={item.id} className={selected ? 'selected' : ''} disabled={unavailable || (selected && selectedIds.length <= 2)} onClick={() => toggleParticipant(item.id)} aria-pressed={selected}>
            {character && <img src={character.portrait} alt="" />}<span><b>{item.name}</b><small>{item.mbti}</small></span><i>{selected ? <Icon name="check" size={15} tone="rose" /> : <Icon name="plus" size={15} tone="lavender" />}</i>
          </button>
        })}
      </div>
      <div className="group-chat__history" ref={streamRef} role="log" aria-live="polite">
        {!visibleMemories.length && <div className="group-chat__empty"><b>这处群聊还没有记录</b><span>你的第一句话会带上时间、地点和在场嘉宾，写进每个人各自的记忆。</span></div>}
        {visibleMemories.map((memory, index) => {
          const previous = visibleMemories[index - 1]
          const showPlayer = !previous || previous.conversationId !== memory.conversationId || previous.playerText !== memory.playerText || previous.time !== memory.time
          const speaker = characters.find(character => character.id === memory.characterId)
          return <div className="group-chat__turn" key={memory.id}>
            {showPlayer && <div className="message player"><p>{memory.playerText}</p><small>{memory.locationName} · {memory.time}{memory.participantNames?.length ? ` · 与${memory.participantNames.filter(name => name !== snapshot.player.displayName).join('、')}` : ''}</small></div>}
            <div className="message agent"><b>{speaker?.name || '嘉宾'} · {ATTITUDE_LABELS[memory.attitude] || memory.attitude}</b>{memory.stageDirection && <em>{memory.stageDirection}</em>}<p>{memory.agentReply}</p><small>{memory.summary || '这句话已分别写入角色记忆'}</small></div>
          </div>
        })}
        {busy && <div className="message agent typing"><i /><i /><i /></div>}
      </div>
      <div className="group-chat__prompts" aria-label="群聊开场建议">{promptOptions.map(prompt => <button type="button" key={prompt} onClick={() => setDraft(prompt)}>{prompt}</button>)}</div>
      {error && <p className="group-chat__error" role="alert">{error}</p>}
      <form className="group-chat__composer" onSubmit={submit}>
        <textarea rows={1} maxLength={240} value={draft} onChange={event => setDraft(event.target.value)} placeholder={`对${selectedCharacters.map(character => character.name).join('、') || '在场嘉宾'}说…`} />
        <button type="submit" disabled={busy || selectedIds.length < 2 || !draft.trim()} aria-label="发送群聊消息"><Icon name="arrow-up-right" size={22} /></button>
      </form>
      <p className="group-chat__rule">群聊只可邀请此刻确实在 {venue.locationName} 的嘉宾；不会补写不在场的人。</p>
    </section>
  </div>
}

function Cinematic({ src, title, identityCards, identityTimeline, onDone }: { src: string; title: string; identityCards?: SceneIdentityCard[]; identityTimeline?: SceneIdentityTimeline[]; onDone: () => void }) {
  const [ready, setReady] = useState(false)
  const [showTitle, setShowTitle] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const videoRef = useRef<HTMLVideoElement>(null)
  const playback = useEventPlayback(videoRef, src, true)
  useEffect(() => {
    if (!ready) return
    setShowTitle(true)
    const timer = window.setTimeout(() => setShowTitle(false), 2600)
    return () => window.clearTimeout(timer)
  }, [ready, src])
  return (
    <div className="cinematic-overlay" role="dialog" aria-modal="true" aria-label={title} data-playback-mode="first-pass-autoclose">
      <video ref={videoRef} src={src} autoPlay muted={playback.muted} playsInline onCanPlay={() => setReady(true)} onTimeUpdate={event => setCurrentTime(event.currentTarget.currentTime)} onEnded={onDone} onError={onDone} />
      <div className="cinematic-grade" />
      {ready && !!identityCards?.length && <SceneIdentitySequence cards={identityCards} sceneKey={src} timeline={identityTimeline} currentTime={currentTime} context="本幕嘉宾" className="scene-identity-plate--cinematic" />}
      <div className={`cinematic-title ${showTitle ? 'show' : ''}`}><span>HEART JOURNEY · STORY EVENT</span><b>{title}</b></div>
      <div className="cinematic-controls">
        <button type="button" className={playback.needsGesture ? 'audio-attention' : ''} onClick={playback.toggleSound} aria-label={playback.muted ? '开启视频声音' : '关闭视频声音'} aria-pressed={!playback.muted}><span aria-hidden="true"><Icon name={playback.muted ? 'volume-off' : 'volume-on'} tone="rose" /></span>{playback.soundLabel}</button>
        <button type="button" onClick={onDone}>跳过<Icon name="arrow-right" size={16} /></button>
      </div>
    </div>
  )
}

function ReceiptToast({ receipt }: { receipt: Receipt }) {
  const patchCount = Object.keys(receipt.patch || {}).length
  const title = receipt.eventActivation ? `事件激活 · ${receipt.eventActivation.label}` : receipt.kind === 'agent-turn' ? `态度更新 · ${ATTITUDE_LABELS[receipt.attitude || ''] || receipt.attitude}` : receipt.kind === 'story-event' ? `新主任务 · ${receipt.mission?.title || receipt.title}` : receipt.kind === 'story-director-wait' ? '导演判断 · 继续积累证据' : receipt.kind === 'story-mission-resolution' ? '主任务结果已写入' : '选择已写入故事'
  const detail = receipt.eventActivation?.text || receipt.mission?.prompt || receipt.playerMissionPrompt || receipt.publicReason || (patchCount ? `${patchCount} 项关系参数已提交` : '剧情状态已提交')
  return <div className="receipt-toast"><HeartMark small /><div><b>{title}</b><span>{detail}</span></div></div>
}

function DirectorMission({ mission, characters, busy, onResolve }: { mission: StoryMission; characters: Character[]; busy: boolean; onResolve: (outcome: 'completed' | 'declined') => void }) {
  const names = mission.participantIds.map(id => characters.find(character => character.id === id)?.name).filter(Boolean).join('、')
  return (
    <section className={`director-mission director-mission--${mission.urgency}`}>
      <div className="director-mission__label"><span>MAIN QUEST</span><i>{mission.deadline}</i></div>
      <h2>{mission.title}</h2>
      <p>{mission.bridgeText}</p>
      {mission.sceneSetup && <div className="director-mission__setup"><b>现场发生了什么</b><span>{mission.sceneSetup}</span></div>}
      {mission.reversalBeat && <div className="director-mission__reversal"><b>意外变化</b><span>{mission.reversalBeat}</span>{mission.characterInsight && <small>{mission.characterInsight}</small>}</div>}
      <div className="director-mission__objective"><b>现在去做</b><span>{mission.prompt}</span></div>
      {!!mission.availableStrategies?.length && <div className="director-mission__strategies"><b>你可采用的策略</b>{mission.availableStrategies.map(item => <span key={item}>· {item}</span>)}</div>}
      <div className="director-mission__meta"><span>{names || '心动小屋'}</span><small>完成证据：{mission.successEvidence}</small></div>
      <div className="director-mission__actions">
        <button disabled={busy} onClick={() => onResolve('completed')}>我已完成</button>
        <button disabled={busy} onClick={() => onResolve('declined')}>这次不参加</button>
      </div>
      <small className="director-mission__exit">退出路径：{mission.exit}</small>
    </section>
  )
}

function GameBrief({ brief }: { brief: NonNullable<StoryNode['gameBrief']> }) {
  return <section className="game-brief">
    <div className="game-brief__title"><span>本轮游戏</span><h2>{brief.name}</h2></div>
    <dl><div><dt>怎么玩</dt><dd>{brief.format}</dd></div><div><dt>怎样算赢</dt><dd>{brief.winCondition}</dd></div></dl>
  </section>
}

function resolveSceneMedia(view: View, guidedCharacterId?: string | null) {
  const { snapshot, node, characters } = view
  const legacyNodeId: Record<string, string> = { arrival: 'arrival-context', 'first-look': 'introductions', 'private-window': 'guided-chat', 'event-reveal': 'team-up', 'heart-message': 'anonymous-letter' }
  const projectedNodeId = legacyNodeId[snapshot.nodeId] || snapshot.nodeId
  const nodeAsset = NODE_MEDIA[projectedNodeId] || NODE_MEDIA['arrival-context']
  const eventId = snapshot.storyMission?.eventId || node.eventId || (snapshot.activeEventId && EVENT_MEDIA[snapshot.activeEventId] ? snapshot.activeEventId : undefined)
  const eventAsset = eventId ? EVENT_MEDIA[eventId] : undefined
  const missionMedia = snapshot.storyMission?.media
  const perspectiveCharacter = characters.find(character => character.id === snapshot.player.perspectiveCharacterId)
  const perspectiveFallbackSrc = perspectiveCharacter?.video?.trim() || ''
  const perspectiveFallbackPoster = perspectiveCharacter?.portrait
  const missionMediaReady = !!missionMedia?.src && missionMedia.available !== false && missionMedia.status !== 'planned'
  const nodeMediaReady = !!node.media?.src && node.media.available !== false && node.media.status !== 'planned'
  const explicitNodeSrc = node.sceneVideo || node.backgroundVideo || (nodeMediaReady ? node.media?.src : undefined)
  const guidedCharacter = projectedNodeId === 'guided-chat' && guidedCharacterId
    ? characters.find(character => character.id === guidedCharacterId)
    : undefined
  // The backend resolver owns cast identity. Never resurrect a static Jiangmi
  // event table when the committed mission says its exact variant is missing.
  if (snapshot.storyMission && eventAsset) {
    const safeFallbackSrc = missionMedia?.fallback?.src || perspectiveFallbackSrc
    const safeFallbackPoster = missionMedia?.fallback?.poster || perspectiveFallbackPoster
    return {
      src: (missionMediaReady ? missionMedia?.src : undefined) || safeFallbackSrc,
      poster: (missionMediaReady ? missionMedia?.poster : undefined) || safeFallbackPoster,
      fallbackSrc: safeFallbackSrc,
      fallbackPoster: safeFallbackPoster,
      assetId: missionMedia?.assetId || (perspectiveCharacter ? `CHAR-${perspectiveCharacter.id}-portrait` : eventAsset.assetId),
      cue: snapshot.storyMission.visualCue || eventAsset.cue || node.mediaCue || node.action,
      identityCards: missionMedia?.identityCards,
      identityTimeline: missionMedia?.identityTimeline,
    }
  }
  if (snapshot.storyMission && missionMediaReady && missionMedia?.src) return {
    src: missionMedia.src,
    poster: missionMedia.poster,
    fallbackSrc: missionMedia.fallback?.src || perspectiveFallbackSrc,
    fallbackPoster: missionMedia.fallback?.poster || perspectiveFallbackPoster,
    assetId: missionMedia.assetId,
    cue: snapshot.storyMission.visualCue || node.mediaCue || node.action,
    identityCards: missionMedia.identityCards,
    identityTimeline: missionMedia.identityTimeline,
  }
  if (explicitNodeSrc) return {
    src: explicitNodeSrc,
    poster: node.poster || node.media?.poster || perspectiveFallbackPoster,
    fallbackSrc: node.media?.fallback?.src || perspectiveFallbackSrc,
    fallbackPoster: node.media?.fallback?.poster || perspectiveFallbackPoster,
    assetId: node.media?.assetId || nodeAsset.assetId,
    cue: node.mediaCue || node.action,
    identityCards: node.media?.identityCards,
    identityTimeline: node.media?.identityTimeline,
  }
  if (guidedCharacter?.video) return {
    src: guidedCharacter.video,
    poster: guidedCharacter.portrait,
    fallbackSrc: perspectiveFallbackSrc,
    fallbackPoster: perspectiveFallbackPoster,
    assetId: `CHAR-${guidedCharacter.id}-guided-scene`,
    cue: node.mediaCue || node.action || `${guidedCharacter.name}停下手边的事，正在等你开口`,
    identityCards: [identityCardFromCharacter(guidedCharacter)],
  }
  if (node.cinematic) return {
    src: node.cinematic,
    poster: node.poster || node.media?.poster || perspectiveFallbackPoster,
    fallbackSrc: node.media?.fallback?.src || perspectiveFallbackSrc,
    fallbackPoster: node.media?.fallback?.poster || perspectiveFallbackPoster,
    assetId: nodeAsset.assetId,
    cue: node.mediaCue || node.action,
    identityCards: node.media?.identityCards,
    identityTimeline: node.media?.identityTimeline,
  }
  const safeFallbackSrc = node.media?.fallback?.src || perspectiveFallbackSrc
  const safeFallbackPoster = node.media?.fallback?.poster || perspectiveFallbackPoster
  return {
    src: safeFallbackSrc,
    poster: safeFallbackPoster,
    fallbackSrc: safeFallbackSrc,
    fallbackPoster: safeFallbackPoster,
    assetId: node.media?.assetId || (perspectiveCharacter ? `CHAR-${perspectiveCharacter.id}-portrait` : nodeAsset.assetId),
    cue: node.mediaCue || node.action || nodeAsset.cue,
    identityCards: node.media?.identityCards || (perspectiveCharacter ? [identityCardFromCharacter(perspectiveCharacter)] : undefined),
    identityTimeline: node.media?.identityTimeline,
  }
}

function Game({ view, onView, onRestart }: { view: View; onView: (view: View) => void; onRestart: () => Promise<void> }) {
  const { snapshot, node, characters } = view
  const [chatCharacter, setChatCharacter] = useState<Character | null>(null)
  const [chatContext, setChatContext] = useState<ConversationContext | null>(null)
  const [groupVenue, setGroupVenue] = useState<ChatVenue | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [cinematic, setCinematic] = useState<string | null>(node.cinematic || null)
  const [cinematicTitle, setCinematicTitle] = useState(node.title || '新的故事开始')
  const [cinematicPreviewedSrc, setCinematicPreviewedSrc] = useState<string | null>(null)
  const autoOpenedChatRef = useRef<string | null>(null)
  const perspectiveId = snapshot.player.perspectiveCharacterId || characters.find(character => character.isPlayerPerspective)?.id
  const perspectiveCharacter = characters.find(character => character.id === perspectiveId)
  const nodeCharacter = characters.find(character => character.id === (node.speakerCharacterId || node.characterId))
  const activeCharacter = nodeCharacter?.id === perspectiveId ? undefined : nodeCharacter
  const sceneIdentityCharacter = activeCharacter || perspectiveCharacter
  const activeSceneContext = sceneContext(node, snapshot)
  const narrationBeats = useMemo(() => buildNarrationBeats(node.text || '', node.textBeats), [node.text, node.textBeats])
  const presentationKey = `${snapshot.nodeId}:${node.title}:${narrationBeats.join('\u241e')}`
  // A cinematic is an authored reading beat, not merely a visual layer. Keep
  // narration at its first frame until the one-shot film naturally ends (or
  // the viewer explicitly skips it), then begin the typewriter from character
  // one. This prevents the passage from completing unseen behind the overlay.
  const typewriter = useTypewriter(narrationBeats, presentationKey, !!cinematic)
  const storyOverlayPhase = useStoryOverlayPhase(typewriter.readyForChoices, presentationKey)
  const guidedCandidateId = resolveGuidedCharacterId(view)
  const guidedCharacterId = guidedCandidateId && guidedCandidateId !== perspectiveId && characters.some(character => character.id === guidedCandidateId) ? guidedCandidateId : null
  const resolvedSceneMedia = resolveSceneMedia(view, guidedCharacterId)
  const liveCharacterIds = new Set(characters.map(character => character.id))
  const hasOutOfCastAuthoredIdentity = (resolvedSceneMedia.identityCards || []).some(identity => {
    const characterId = identity.characterId || identity.id
    return !!characterId && !liveCharacterIds.has(characterId)
  })
  // Defensive compatibility for an older cached API payload: never keep
  // playing footage that names somebody outside this season's live cast.
  const sceneMedia = hasOutOfCastAuthoredIdentity && perspectiveCharacter ? {
    ...resolvedSceneMedia,
    src: resolvedSceneMedia.fallbackSrc || perspectiveCharacter.video || '',
    poster: resolvedSceneMedia.fallbackPoster || perspectiveCharacter.portrait,
    assetId: `CHAR-${perspectiveCharacter.id}-portrait`,
    identityCards: [identityCardFromCharacter(perspectiveCharacter)],
    identityTimeline: [],
  } : resolvedSceneMedia
  const authoredIdentityCards = sceneMedia.identityCards || []
  const authoredIdentityTimeline = sceneMedia.identityTimeline || []
  const sceneIdentityCards = authoredIdentityCards.length ? authoredIdentityCards.map(identity => {
    const character = characters.find(item => item.id === identity.characterId || item.id === identity.id)
    return {
      ...(character ? identityCardFromCharacter(character) : {}),
      ...identity,
      characterId: identity.characterId || identity.id || character?.id,
      accent: identity.accent || character?.accent,
      tagline: identity.tagline || character?.tagline,
    } as SceneIdentityCard
  }) : (sceneIdentityCharacter ? [identityCardFromCharacter(sceneIdentityCharacter)] : [])
  const sceneIdentityKey = `${snapshot.nodeId}:${sceneMedia.assetId || sceneMedia.src}`
  const [scenePlaybackTime, setScenePlaybackTime] = useState(0)
  useEffect(() => setScenePlaybackTime(0), [sceneIdentityKey])
  const pendingChat = resolvePendingChat(view)
  const pendingAutoOpen = !!pendingChat && (typeof pendingChat !== 'object' || (pendingChat.autoOpen !== false && pendingChat.status !== 'completed'))
  const pendingToken = typeof pendingChat === 'object' && pendingChat?.id ? pendingChat.id : `${snapshot.runId}:${snapshot.nodeId}:${guidedCharacterId}`
  const availableChoices = node.choices.filter(choice => (choice.characterId || choice.targetCharacterId) !== perspectiveId)
  const contextForCharacter = (characterId: string): ConversationContext => {
    const venue = view.chatContexts?.venues.find(candidate => candidate.characters.some(character => character.id === characterId))
    return {
      time: venue?.time || view.chatContexts?.scene?.time || activeSceneContext.time,
      locationId: venue?.locationId || view.chatContexts?.scene?.locationId || activeSceneContext.locationId,
      locationName: venue?.locationName || view.chatContexts?.scene?.locationName || activeSceneContext.locationName,
      participantIds: [perspectiveId, characterId].filter((value): value is string => !!value),
      channel: '1v1',
    }
  }
  useEffect(() => {
    if (!typewriter.readyForChoices || !guidedCharacterId || !pendingAutoOpen || autoOpenedChatRef.current === pendingToken) return
    const target = characters.find(character => character.id === guidedCharacterId)
    if (!target) return
    autoOpenedChatRef.current = pendingToken
    setChatContext(contextForCharacter(target.id))
    setChatCharacter(target)
  }, [characters, guidedCharacterId, pendingAutoOpen, pendingToken, typewriter.readyForChoices, view.chatContexts])
  const choose = async (choice: Choice, customText = '') => {
    if (!typewriter.readyForChoices) return
    unlockAudioIntent()
    setBusy(true); setError('')
    try {
      const result = await api<View & { receipt: Receipt }>(`/api/runs/${snapshot.runId}/choices`, {
        method: 'POST', body: JSON.stringify({
          choiceId: choice.id,
          characterId: choice.characterId || choice.targetCharacterId,
          revision: snapshot.revision,
          ...(customText ? { customText, heartMessage: node.characterChoice ? customText : undefined } : {}),
        })
      })
      setReceipt(result.receipt); setTimeout(() => setReceipt(null), 3300)
      onView(result)
      if (result.node.cinematic) { setCinematicPreviewedSrc(null); setCinematicTitle(result.node.title || '新的故事开始'); setCinematic(result.node.cinematic) }
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const send = async (message: string, context: ConversationContext) => {
    if (!chatCharacter) return
    setBusy(true); setError('')
    try {
      const result = await api<View & { receipt: Receipt }>(`/api/runs/${snapshot.runId}/agents/${chatCharacter.id}/messages`, {
        method: 'POST', body: JSON.stringify({ message, revision: snapshot.revision, context })
      })
      setReceipt(result.receipt); setTimeout(() => setReceipt(null), 3300)
      onView(result)
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const sendGroup = async (message: string, participantIds: string[], context: ConversationContext) => {
    setBusy(true); setError('')
    try {
      const result = await api<View & { replies: GroupReply[]; receipts: Receipt[]; context: ConversationContext }>(`/api/runs/${snapshot.runId}/group-messages`, {
        method: 'POST', body: JSON.stringify({ message, participantIds, revision: snapshot.revision, context })
      })
      const firstReceipt = result.receipts?.[0]
      if (firstReceipt) { setReceipt(firstReceipt); setTimeout(() => setReceipt(null), 3300) }
      onView(result)
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const directStory = async () => {
    unlockAudioIntent()
    setBusy(true); setError('')
    try {
      const result = await api<View & { receipt: Receipt }>(`/api/runs/${snapshot.runId}/story-director`, {
        method: 'POST', body: JSON.stringify({ revision: snapshot.revision })
      })
      setReceipt(result.receipt); setTimeout(() => setReceipt(null), 4300); onView(result)
      if (result.receipt.kind === 'story-event' && result.receipt.mission?.media?.src) {
        setCinematicPreviewedSrc(null)
        setCinematicTitle(result.receipt.mission.title || result.receipt.title || '新的主任务')
        setCinematic(result.receipt.mission.media.src)
      }
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const resolveMission = async (outcome: 'completed' | 'declined') => {
    if (!snapshot.storyMission) return
    unlockAudioIntent()
    setBusy(true); setError('')
    try {
      const result = await api<View & { receipt: Receipt }>(`/api/runs/${snapshot.runId}/story-missions/${snapshot.storyMission.id}/resolve`, {
        method: 'POST', body: JSON.stringify({ revision: snapshot.revision, outcome, evidence: outcome === 'completed' ? '玩家确认已完成当前可执行任务' : '玩家使用了事件模板提供的退出路径' })
      })
      setReceipt(result.receipt); setTimeout(() => setReceipt(null), 3300); onView(result)
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const restart = async () => {
    if (busy) return
    setBusy(true)
    try { await onRestart() }
    finally { setBusy(false) }
  }
  const memoriesDone = snapshot.echoMemories.length > 0
  const eventDone = !!snapshot.activeEventId
  const guidedInteractionDone = typeof pendingChat === 'object' && pendingChat?.status === 'completed'
  const guidedMemoryDone = !!guidedCharacterId && snapshot.echoMemories.some(memory => memory.characterId === guidedCharacterId)
  const interactionHasMemory = guidedCharacterId ? guidedMemoryDone : memoriesDone
  const requiredInteractionDone = guidedInteractionDone || guidedMemoryDone
  const directorAvailable = node.allowDirector === true || (snapshot.storyArc.phase === 'late' && !node.isEnding)
  return (
    <main className="game-shell game-shell--immersive">
      <header className="game-topbar">
        <div><span>心动之旅</span><small>{node.chapter}</small></div>
        <div className="game-progress"><i style={{ width: `${PROGRESS[snapshot.nodeId] || 0}%` }} /></div>
        <button className="signal-button" aria-label="关系状态"><HeartMark small /><span>{snapshot.flags.heat + snapshot.echoMemories.length}</span></button>
      </header>
      <section className="scene-stage">
        <SceneMedia src={sceneMedia.src} poster={sceneMedia.poster} fallbackSrc={sceneMedia.fallbackSrc} fallbackPoster={sceneMedia.fallbackPoster} assetId={sceneMedia.assetId} cue={sceneMedia.cue} active={!chatCharacter && !groupVenue && !cinematic} firstPassConsumed={cinematicPreviewedSrc === sceneMedia.src} onTimeUpdate={setScenePlaybackTime} />
        <div className="scene-atmosphere" />
        <div className="scene-time"><span>{node.eyebrow}</span><i /></div>
        {!!sceneIdentityCards.length && <SceneIdentitySequence
          cards={sceneIdentityCards}
          sceneKey={sceneIdentityKey}
          timeline={authoredIdentityTimeline}
          currentTime={scenePlaybackTime}
          context={authoredIdentityCards.length || activeCharacter ? '嘉宾登场' : '你的视角'}
        />}
      </section>
      <div className="story-overlay-zone">
      <section className={`story-card story-card--${storyOverlayPhase}`} data-story-phase={storyOverlayPhase}>
        {storyOverlayPhase !== 'interaction' && <div className="story-narration-layer" data-story-layer="narration">
          <div className="story-card__chapter"><span>{node.speaker}</span><i /></div>
          <button className="story-narration" type="button" onClick={typewriter.reveal} aria-label={`${node.title}。第${typewriter.beatIndex + 1}段，共${typewriter.beatCount}段。${typewriter.text}。${typewriter.complete ? '轻触继续。' : '轻触补全本段。'}`}>
            <h1>{node.title}</h1>
            <p data-beat={`${typewriter.beatIndex + 1}/${typewriter.beatCount}`}>{typewriter.text}<i className={typewriter.complete ? 'typewriter-cursor complete' : 'typewriter-cursor'} aria-hidden="true" /></p>
            <small className="story-continue-hint">{!typewriter.complete ? `轻触补全本段 · ${typewriter.beatIndex + 1}/${typewriter.beatCount}` : typewriter.isLastBeat ? '再轻触一次，进入选择' : `轻触继续下一段 · ${typewriter.beatIndex + 1}/${typewriter.beatCount}`}</small>
          </button>
        </div>}
        {storyOverlayPhase === 'interaction' && <div className="story-reveal" data-story-layer="interaction">
          {snapshot.nodeId === 'callback' && <HeartInboxPhone snapshot={snapshot} characters={characters} />}
          {node.gameBrief && <GameBrief brief={node.gameBrief} />}
          {snapshot.storyMission ? <DirectorMission mission={snapshot.storyMission} characters={characters} busy={busy} onResolve={resolveMission} /> : directorAvailable && memoriesDone && <button className="director-trigger" disabled={busy} onClick={directStory}><span><b>让剧情导演读取此刻的关系证据</b><small>从已研究的恋综事件库中激活下一项主任务</small></span><i>{busy ? '…' : <Icon name="arrow-up-right" size={18} />}</i></button>}
          {(node.requiresMemory || node.requiresGuidedInteraction) && <div className={`link-proof ${(node.requiresGuidedInteraction ? requiredInteractionDone : eventDone) ? 'done' : ''} ${guidedCharacterId && !requiredInteractionDone ? 'guided' : ''}`}>
            <span>{node.requiresGuidedInteraction && requiredInteractionDone ? <Icon name="check" size={17} /> : eventDone ? <Icon name="check" size={17} /> : interactionHasMemory ? '02' : '01'}</span><div><b>{node.requiresGuidedInteraction && requiredInteractionDone ? '破冰对话已完成，现在轮到你决定怎样邀请' : eventDone ? '专属事件已经进入正片' : interactionHasMemory ? '继续交流，让对方作出一个具体选择' : guidedCharacterId ? `剧情正在等你与${characters.find(character => character.id === guidedCharacterId)?.name || '指定嘉宾'}开口` : '先完成一次 1 对 1 交流'}</b><small>{node.requiresGuidedInteraction && requiredInteractionDone ? '对方已经记住你们的第一次真实来回' : eventDone ? snapshot.eventLedger[snapshot.eventLedger.length - 1]?.label : interactionHasMemory ? '角色会依据人物卡决定是否交出线索或邀约' : guidedCharacterId ? '下方对应头像已点亮“1”，先从自我介绍和寒暄开始' : '从一声招呼开始，不用一上来就谈任务'}</small></div>
          </div>}
          {!!availableChoices.length && <section className={`choice-section ${node.characterChoice ? 'choice-section--cast' : ''}`} aria-label="剧情选择">
            <div className="choice-section__heading"><span>{node.characterChoice ? '今晚，你想把心动短信发给谁？' : '这一刻，你准备怎么做？'}</span><small>你的选择会改变接下来的相处</small></div>
            {node.characterChoice ? <HeartMessageComposer choices={availableChoices} characters={characters} busy={busy} disabled={(!!node.requiresGuidedInteraction && !requiredInteractionDone) || (!!node.requiresMemory && !memoriesDone) || (!!node.requiresEvent && !eventDone)} onSend={choose} /> : <>
            <div className={`choice-stack ${snapshot.nodeId === 'icebreaker-choice' ? 'choice-stack--icebreaker' : ''} ${snapshot.nodeId !== 'icebreaker-choice' && availableChoices.every(choice => choice.characterId || choice.targetCharacterId) ? 'choice-stack--character-grid' : ''}`}>
              {availableChoices.map((choice, index) => {
                const choiceCharacterId = choice.characterId || choice.targetCharacterId
                const character = choiceCharacterId ? characters.find(c => c.id === choiceCharacterId) : null
                return (
                  <button key={choice.id} className={character && snapshot.nodeId !== 'icebreaker-choice' ? 'choice-button--character' : undefined} disabled={busy || (!!node.requiresGuidedInteraction && !requiredInteractionDone) || (!!node.requiresMemory && !memoriesDone) || (!!node.requiresEvent && !eventDone)} onClick={() => choose(choice)} style={character ? { '--accent': character.accent } as React.CSSProperties : undefined}>
                    {snapshot.nodeId === 'icebreaker-choice' && character ? <>
                      <span className="icebreaker-card__top"><em>三分钟生活观察卡</em><i>{String(index + 1).padStart(2, '0')}</i></span>
                      <span className="icebreaker-card__person"><img src={character.portrait} alt={`${character.name}头像`} /><span><b>{character.name}<em>{character.mbti}</em></b><small>{publicOccupation(character)} · {character.tagline}</small></span></span>
                      <span className="icebreaker-card__action"><em>你要做什么</em><b>{choice.label}</b></span>
                      <span className="icebreaker-card__question"><em>三分钟内，问到这件小事</em><span>{choice.hint || character.independentInterest}</span></span>
                      <i className="icebreaker-card__arrow"><Icon name="arrow-right" size={18} /></i>
                    </> : character ? <>
                      <img className="choice-character-photo" src={character.portrait} alt={`${character.name}头像`} />
                      <span className="choice-copy choice-copy--character">
                        <span className="choice-character-identity"><b>{character.name}</b><em>{publicOccupation(character)} · {character.mbti}</em></span>
                        <small className="choice-character-personality">{character.tagline}</small>
                        <strong>{choice.label}</strong>
                        <small>{choice.hint}</small>
                      </span>
                      <i><Icon name="arrow-right" size={18} tone="rose" /></i>
                    </> : <>
                      <span className="choice-index">{String(index + 1).padStart(2, '0')}</span>
                      <span className="choice-copy"><b>{choice.label}</b><small>{choice.hint}</small></span><i><Icon name="arrow-right" size={18} tone="rose" /></i>
                    </>}
                  </button>
                )
              })}
            </div>
            <FreeChoiceComposer choices={availableChoices} busy={busy} disabled={(!!node.requiresGuidedInteraction && !requiredInteractionDone) || (!!node.requiresMemory && !memoriesDone) || (!!node.requiresEvent && !eventDone)} onSend={choose} />
            </>}
          </section>}
          {node.isEnding && <div className="ending-proof"><span>首个联通闭环已完成</span><p>你的文字选择进入角色记忆，并在剧情回声中触发了新的表达。</p><button disabled={busy} onClick={restart}>{busy ? '正在重启心动信号…' : '重新开始一段旅程'}</button></div>}
          {error && <p className="error-note">{error}</p>}
        </div>}
      </section>
      </div>
      <CharacterDock
        characters={characters}
        snapshot={snapshot}
        chatContexts={view.chatContexts}
        guidedCharacterId={typewriter.readyForChoices ? guidedCharacterId : null}
        guidedComplete={node.requiresGuidedInteraction ? requiredInteractionDone : node.requiresEvent ? eventDone : memoriesDone}
        groupDisabled={snapshot.nodeId === 'guided-chat' && !requiredInteractionDone}
        currentLocation={activeSceneContext.location}
        currentTime={activeSceneContext.time}
        onOpen={(character, context) => { setError(''); setGroupVenue(null); setChatContext(context); setChatCharacter(character) }}
        onOpenGroup={venue => { setError(''); setChatCharacter(null); setChatContext(null); setGroupVenue(venue) }}
      />
      {chatCharacter && chatCharacter.id !== perspectiveId && <ChatSheet key={chatCharacter.id} character={chatCharacter} characters={characters} snapshot={snapshot} embeddedOpener={view.chatOpeners?.[chatCharacter.id] || snapshot.chatOpeners?.[chatCharacter.id]} context={chatContext || contextForCharacter(chatCharacter.id)} error={error} onClose={() => { setChatCharacter(null); setChatContext(null) }} onSend={send} busy={busy} />}
      {groupVenue && <GroupChatSheet key={`${groupVenue.locationId}:${snapshot.nodeId}`} venue={groupVenue} characters={characters} snapshot={snapshot} onClose={() => setGroupVenue(null)} onSend={sendGroup} busy={busy} error={error} />}
      {cinematic && <Cinematic src={cinematic} title={cinematicTitle} identityCards={sceneIdentityCards} identityTimeline={authoredIdentityTimeline} onDone={() => { setCinematicPreviewedSrc(cinematic); setCinematic(null) }} />}
      {receipt && <ReceiptToast receipt={receipt} />}
    </main>
  )
}

export default function App() {
  const [characters, setCharacters] = useState<Character[]>([])
  const [view, setView] = useState<View | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [authError, setAuthError] = useState('')
  const [startError, setStartError] = useState('')
  const startRequestInFlight = useRef(false)
  useEffect(() => {
    api<{ characters: Character[]; view: View | null }>('/api/bootstrap')
      .then(data => { setCharacters(data.characters); setView(new URLSearchParams(location.search).get('intro') === '1' ? null : data.view) })
      .catch(error => setAuthError(error.message))
      .finally(() => setLoading(false))
  }, [])
  const cast = useMemo(() => view?.characters || characters, [view, characters])
  const start = async (mbti: string, perspectiveCharacterId?: string) => {
    if (startRequestInFlight.current) return
    startRequestInFlight.current = true
    setBusy(true)
    setStartError('')
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 25_000)
    try {
      setView(await api<View>('/api/runs', { method: 'POST', body: JSON.stringify({ mbti, perspectiveCharacterId }), signal: controller.signal }))
    } catch (error) {
      const requestError = error as Error
      const message = requestError.name === 'AbortError'
        ? '开启等待超过 25 秒，连接已停止。请检查网络后再试；刚才的按钮只提交了一次。'
        : requestError.message
      if (view) setAuthError(message)
      else setStartError(message)
    } finally {
      window.clearTimeout(timeout)
      startRequestInFlight.current = false
      setBusy(false)
    }
  }
  if (loading) return <Loading />
  if (authError) return <LoginGate message={authError} />
  if (!view) return <Landing characters={cast} onStart={start} busy={busy} startError={startError} />
  return <Game view={view} onView={setView} onRestart={() => start(view.snapshot.player.mbti, view.snapshot.player.perspectiveCharacterId)} />
}
