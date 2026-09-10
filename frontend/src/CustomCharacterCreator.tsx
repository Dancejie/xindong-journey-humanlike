import { FormEvent, useEffect, useRef, useState } from 'react'
import { Icon } from './ui/Icon'
import './custom-character.css'

type VideoGeneration = {
  available: boolean; estimatedCostCny: number | null; durationSeconds: number
  reason?: string; modelLabel?: string; resolution?: string; autoSubmit?: boolean
}

export type CustomCharacterProfile = {
  id: string
  character: {
    id: string; name: string; mbti: string; gender?: string; portrait: string
    video?: string; occupation?: string; tagline?: string; isCustom?: boolean
  }
  cardPreview: { introduction: string; voice: string; boundary: string; preferences: string; source?: string }
  video: { status: string; message?: string; videoUrl?: string; durationSeconds?: number | null; requestedModel?: string | null; usedModel?: string | null; resolution?: string | null }
  generation: VideoGeneration
}

type Api = <T>(path: string, options?: RequestInit) => Promise<T>
type Props = {
  active: boolean
  api: Api
  initialMbti: string
  providerLabel: string
  onBack: () => void
  onStart: (profile: CustomCharacterProfile) => void
  starting: boolean
  startError?: string
}

const MBTIS = ['INTJ', 'INTP', 'ENTJ', 'ENTP', 'INFJ', 'INFP', 'ENFJ', 'ENFP', 'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ', 'ISTP', 'ISFP', 'ESTP', 'ESFP']
const PROCESSING = new Set(['reserved', 'submitted', 'processing', 'queued'])
const CANDIDATE = new Set(['candidate', 'generated-candidate', 'succeeded'])
const APPROVED = new Set(['approved', 'approved-runtime', 'runtime-integrated'])
const modelName = (model: string) => ({ 'seedance-2.0': 'Seedance 2.0', 'seedance-2.0-mini': 'Seedance 2.0 Mini' })[model] || model

function CustomVideoPreview({ src, poster }: { src: string; poster: string }) {
  const inline = useRef<HTMLVideoElement>(null)
  const expanded = useRef<HTMLVideoElement>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const resume = useRef({ time: 0, playing: false, muted: false, volume: 1 })
  const enlarge = () => {
    const video = inline.current
    if (!video || !expanded.current || !dialog.current) return
    resume.current = { time: video.ended ? 0 : video.currentTime, playing: !video.paused, muted: video.muted, volume: video.volume }
    video.pause()
    dialog.current.showModal()
    expanded.current.preload = 'metadata'
    expanded.current.load()
  }
  const restorePlayback = () => {
    const video = expanded.current
    if (!video || !dialog.current?.open) return
    video.currentTime = resume.current.time
    video.muted = resume.current.muted
    video.volume = resume.current.volume
    if (resume.current.playing) void video.play().catch(() => {})
  }
  const stopExpanded = () => {
    const video = expanded.current
    if (!video) return
    video.pause()
    if (inline.current && inline.current.readyState > 0 && video.readyState > 0) inline.current.currentTime = video.currentTime
  }
  return <div className="custom-video-viewer">
    <video ref={inline} className="custom-video-preview" src={src} poster={poster} controls playsInline preload="metadata" aria-label="你的动态形象预览" />
    <button type="button" className="custom-secondary-button" onClick={enlarge}>放大查看完整视频</button>
    <p className="custom-help custom-centered">完整画幅 · 不裁切；可放大查看表情和动作。</p>
    <dialog ref={dialog} className="custom-video-dialog" aria-label="完整动态形象预览" onClose={stopExpanded}>
      <div className="custom-video-dialog-header"><strong>你的动态形象 · 完整画幅</strong><button type="button" className="custom-text-button" autoFocus onClick={() => dialog.current?.close()}>关闭预览</button></div>
      <video ref={expanded} src={src} poster={poster} controls playsInline preload="none" onLoadedMetadata={restorePlayback} aria-label="完整画幅视频" />
      <p className="custom-help">仅放大现有视频，不重新生成。</p>
    </dialog>
  </div>
}

export function CustomCharacterCreator({ active, api, initialMbti, providerLabel, onBack, onStart, starting, startError }: Props) {
  const [form, setForm] = useState({ name: '', mbti: '', gender: 'female', age: '', occupation: '', about: '', preferences: '', boundaries: '', photoDataUrl: '', consent: false, autoVideo: true })
  const [step, setStep] = useState<'form' | 'preview'>('form')
  const [profile, setProfile] = useState<CustomCharacterProfile | null>(null)
  const [saved, setSaved] = useState<CustomCharacterProfile[]>([])
  const [generation, setGeneration] = useState<VideoGeneration | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [listError, setListError] = useState('')
  const [statusError, setStatusError] = useState('')
  const [deleteConfirmation, setDeleteConfirmation] = useState(false)
  const [photoLoading, setPhotoLoading] = useState(false)
  const [attemptedStartId, setAttemptedStartId] = useState('')
  const controllers = useRef(new Set<AbortController>())
  const actionInFlight = useRef(false)
  const activeRef = useRef(active)
  const photoReader = useRef<FileReader | null>(null)
  const createRequestId = useRef('')
  const headingRef = useRef<HTMLHeadingElement | null>(null)

  async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 45_000) {
    const controller = new AbortController()
    controllers.current.add(controller)
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)
    try { return await api<T>(path, { ...options, signal: controller.signal }) }
    finally { window.clearTimeout(timer); controllers.current.delete(controller) }
  }

  const update = (key: keyof typeof form, value: string | boolean) => {
    createRequestId.current = ''
    setForm(previous => ({ ...previous, [key]: value }))
  }
  const remember = (next: CustomCharacterProfile) => {
    setProfile(next)
    setGeneration(next.generation)
    setSaved(previous => [next, ...previous.filter(item => item.id !== next.id)])
  }

  useEffect(() => {
    activeRef.current = active
    if (active) {
      setForm(previous => previous.mbti ? previous : { ...previous, mbti: MBTIS.includes(initialMbti) ? initialMbti : 'ENFP' })
      setListError('')
      request<{ characters: CustomCharacterProfile[]; generation?: VideoGeneration }>('/api/custom-characters')
        .then(result => {
          if (!activeRef.current) return
          setSaved(result.characters)
          setGeneration(result.generation || null)
          setProfile(previous => previous ? result.characters.find(item => item.id === previous.id) || previous : null)
        })
        .catch(reason => { if (activeRef.current && reason.name !== 'AbortError') setListError(reason.message) })
    }
    return () => {
      activeRef.current = false
      controllers.current.forEach(controller => controller.abort())
      photoReader.current?.abort()
    }
  }, [active])

  useEffect(() => {
    if (active) {
      headingRef.current?.focus({ preventScroll: true })
      window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
    }
  }, [active, step])

  useEffect(() => {
    if (!active || !profile || !PROCESSING.has(profile.video.status) || statusError) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const next = await request<CustomCharacterProfile>(`/api/custom-characters/${encodeURIComponent(profile.id)}`)
        if (!cancelled) remember(next)
      } catch (reason) {
        if (!cancelled && (reason as Error).name !== 'AbortError') setStatusError((reason as Error).message)
      }
    }, 5000)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [active, profile, statusError])

  const pickPhoto = async (file?: File) => {
    if (!file) return
    setError('')
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('请选择 JPG、PNG 或 WebP 照片，不支持动图和其他文件。')
      return
    }
    if (!file.size || file.size > 8 * 1024 * 1024) {
      setError('照片需要小于或等于 8 MB，请换一张清晰的单人照片。')
      return
    }
    photoReader.current?.abort()
    setPhotoLoading(true)
    const reader = new FileReader()
    photoReader.current = reader
    reader.onload = () => {
      if (activeRef.current && typeof reader.result === 'string') update('photoDataUrl', reader.result)
      setPhotoLoading(false)
    }
    reader.onerror = () => { setPhotoLoading(false); setError('这张照片没有读成功，请重新选择。') }
    reader.onabort = () => setPhotoLoading(false)
    reader.readAsDataURL(file)
  }

  async function perform(label: string, action: () => Promise<void>) {
    if (actionInFlight.current || starting) return
    actionInFlight.current = true
    setBusy(label)
    setError('')
    try { await action() }
    catch (reason) {
      if (activeRef.current) setError((reason as Error).name === 'AbortError'
        ? '等待时间较长，已停止本次连接。不会自动再次提交；你可以刷新已保存角色或视频状态，查看是否已完成。'
        : (reason as Error).message)
    } finally {
      actionInFlight.current = false
      setBusy('')
    }
  }

  const create = (event: FormEvent) => {
    event.preventDefault()
    if (!form.photoDataUrl) { setError('先上传一张属于你的清晰单人形象照。'); return }
    if (!form.consent) { setError('请确认已成年，并拥有照片使用授权。'); return }
    if (Number(form.age) < 18 || Number(form.age) > 100) { setError('本体验仅供 18 周岁及以上的成年人使用。'); return }
    void perform('create', async () => {
      if (!createRequestId.current) createRequestId.current = crypto.randomUUID()
      const next = await request<CustomCharacterProfile>('/api/custom-characters', {
        method: 'POST', body: JSON.stringify({ ...form, maxCostCny: form.autoVideo && generation?.available ? generation.estimatedCostCny : null, requestId: createRequestId.current, name: form.name.trim(), age: Number(form.age), occupation: form.occupation.trim(), about: form.about.trim(), preferences: form.preferences.trim(), boundaries: form.boundaries.trim() }),
      })
      if (!activeRef.current) return
      remember(next)
      setStep('preview')
      setDeleteConfirmation(false)
      // The normalized server copy is now the identity anchor. Do not retain a
      // second full-size photograph in browser memory after successful upload.
      update('photoDataUrl', '')
    })
  }

  const refreshSaved = () => void perform('refresh', async () => {
    const result = await request<{ characters: CustomCharacterProfile[]; generation?: VideoGeneration }>('/api/custom-characters')
    if (!activeRef.current) return
    setSaved(result.characters)
    setGeneration(result.generation || null)
    setProfile(previous => previous ? result.characters.find(item => item.id === previous.id) || previous : null)
    setListError('')
  })

  const openSaved = (item: CustomCharacterProfile) => {
    setProfile(item)
    setStep('preview')
    setDeleteConfirmation(false)
    setStatusError('')
    setError('')
  }

  const startVideo = () => {
    if (!profile?.generation.available || profile.generation.estimatedCostCny == null || profile.video.status !== 'planned') return
    void perform('video', async () => {
      const next = await request<CustomCharacterProfile>(`/api/custom-characters/${encodeURIComponent(profile.id)}/video`, { method: 'POST', body: JSON.stringify({ confirmed: true, maxCostCny: profile.generation.estimatedCostCny }) })
      if (activeRef.current) { remember(next); setStatusError('') }
    })
  }

  const approveVideo = () => {
    if (!profile) return
    void perform('approve', async () => {
      const next = await request<CustomCharacterProfile>(`/api/custom-characters/${encodeURIComponent(profile.id)}/video/approve`, { method: 'POST', body: '{}' })
      if (activeRef.current) remember(next)
    })
  }

  const refreshProfile = () => {
    if (!profile) return
    void perform('status', async () => {
      const next = await request<CustomCharacterProfile>(`/api/custom-characters/${encodeURIComponent(profile.id)}`)
      if (activeRef.current) { remember(next); setStatusError('') }
    })
  }

  const deleteProfile = () => {
    if (!profile) return
    void perform('delete', async () => {
      await request(`/api/custom-characters/${encodeURIComponent(profile.id)}`, { method: 'DELETE' })
      if (!activeRef.current) return
      setSaved(previous => previous.filter(item => item.id !== profile.id))
      setProfile(null)
      setStep('form')
      setDeleteConfirmation(false)
    })
  }

  if (!active) return null
  const disabled = !!busy || starting
  const videoReady = profile && APPROVED.has(profile.video.status)
  const candidate = profile && CANDIDATE.has(profile.video.status)
  const processing = profile && PROCESSING.has(profile.video.status)
  const autoVideoAvailable = generation?.available && generation.estimatedCostCny != null
  const videoDuration = profile?.video.durationSeconds || profile?.generation.durationSeconds || 10
  const videoResolution = profile?.video.resolution || profile?.generation.resolution || '480p'
  const videoModel = profile?.video.usedModel || profile?.video.requestedModel || profile?.generation.modelLabel || 'Seedance 2.0 Mini'

  return <main className="custom-character-page" data-component="CustomCharacterCreator">
    <header className="custom-character-topbar">
      <button type="button" className="custom-text-button" disabled={starting} onClick={() => { activeRef.current = false; controllers.current.forEach(controller => controller.abort()); onBack() }}><Icon name="arrow-left" size={18} />返回选择</button>
      <span>心动之旅 · 我的角色</span>
    </header>
    <section className="custom-character-heading">
      <span className="custom-eyebrow">YOUR STORY, YOUR WAY</span>
      <h1 ref={headingRef} tabIndex={-1}>{step === 'preview' ? '这次，以你的模样登场。' : '把你自己，带进故事里。'}</h1>
      <p>{step === 'preview' ? '人物卡已经准备好，现在就能开始。动态视频可在下方查看进度，确认形象后用于故事。' : '选择你的 MBTI，留下一点真实的喜好。和熟悉的嘉宾见面、聊天，让彼此慢慢记住你。'}</p>
    </section>

    {error && <div className="custom-feedback custom-feedback--error" role="alert">{error}</div>}

    {step === 'form' ? <>
      {saved.length > 0 && <section className="custom-saved-section" aria-label="我的已保存角色">
        <div className="custom-section-title"><h2>继续使用我的角色</h2><button type="button" className="custom-text-button" disabled={disabled} onClick={refreshSaved}>刷新</button></div>
        <div className="custom-saved-list">{saved.map(item => <button type="button" key={item.id} disabled={disabled} onClick={() => openSaved(item)} className="custom-saved-card">
          <img src={item.character.portrait} alt={`${item.character.name}的形象`} loading="lazy" />
          <span><b>{item.character.name}</b><small>{item.character.mbti} · {APPROVED.has(item.video.status) ? '动态形象已就绪' : PROCESSING.has(item.video.status) ? '视频生成中' : '人物卡已保存'}</small></span>
          <Icon name="arrow-right" size={18} />
        </button>)}</div>
      </section>}
      {listError && <div className="custom-feedback"><p>已保存角色暂时没有读取成功：{listError}</p><button className="custom-text-button" type="button" onClick={refreshSaved} disabled={disabled}>重新读取我的角色</button></div>}
      <form className="custom-character-form glass-card" onSubmit={create}>
        <fieldset disabled={disabled}>
          <legend>01 / 你的形象</legend>
          <label className={`custom-photo-picker ${form.photoDataUrl ? 'custom-photo-picker--selected' : ''}`}>
            {form.photoDataUrl ? <img src={form.photoDataUrl} alt="你上传的形象预览" /> : <span className="custom-photo-placeholder" aria-hidden="true">＋</span>}
            <span><b>{photoLoading ? '正在读取照片…' : form.photoDataUrl ? '重新选择照片' : '上传清晰的单人照'}</b><small>JPG / PNG / WebP · 最大 8 MB<br />建议面部清晰、光线自然，无其他人入镜。</small></span>
            <input aria-label="上传个人形象照" type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { void pickPhoto(event.currentTarget.files?.[0]); event.currentTarget.value = '' }} disabled={photoLoading} />
          </label>
          <p className="custom-help">照片只用于外观参考；不会从长相推断性格、MBTI、职业或经历。请勿上传证件照、证件信息或未成年人照片。</p>
        </fieldset>
        <fieldset disabled={disabled}>
          <legend>02 / 故事中的你</legend>
          <div className="custom-form-grid">
            <label>昵称<input required maxLength={24} autoComplete="off" value={form.name} onChange={event => update('name', event.target.value)} placeholder="希望大家怎么称呼你？" /></label>
            <label>年龄<input required type="number" inputMode="numeric" min={18} max={100} value={form.age} onChange={event => update('age', event.target.value)} placeholder="18 周岁及以上" /></label>
            <label>我的 MBTI<select value={form.mbti || 'ENFP'} onChange={event => update('mbti', event.target.value)}>{MBTIS.map(mbti => <option value={mbti} key={mbti}>{mbti}</option>)}</select></label>
            <label>角色性别<select value={form.gender} onChange={event => update('gender', event.target.value)}><option value="female">女性</option><option value="male">男性</option></select></label>
            <label className="custom-form-full">职业 / 目前在做什么<input maxLength={80} value={form.occupation} onChange={event => update('occupation', event.target.value)} placeholder="例如：产品设计师，最近在学做面包" /></label>
            <label className="custom-form-full">想让嘉宾先认识你的哪一面？<textarea maxLength={600} value={form.about} onChange={event => update('about', event.target.value)} placeholder="例如：慢热，但熟悉以后话很多。周末喜欢散步、拍照。" rows={3} /><small>写你愿意在故事中分享的信息，不需要真名、联系方式或详细住址。</small></label>
          </div>
        </fieldset>
        <fieldset disabled={disabled}>
          <legend>03 / 相处偏好与边界</legend>
          <label>喜欢怎样的相处？<textarea maxLength={500} value={form.preferences} onChange={event => update('preferences', event.target.value)} placeholder="例如：喜欢轻松的玩笑、一起做事；比起查户口，更想听生活里的小事。" rows={3} /></label>
          <label>不喜欢什么？有什么要尊重的边界？<textarea maxLength={500} value={form.boundaries} onChange={event => update('boundaries', event.target.value)} placeholder="例如：不要催我表态，不要叫亲昵称呼；身体接触前先征求同意。" rows={3} /></label>
          <p className="custom-help">这些内容会进入你的角色卡，帮助生成对白与选择。MBTI 是表达参考，你写下的偏好和边界更重要。最多保存 5 位自定义角色。</p>
        </fieldset>
        <section className="custom-video-option" aria-label="动态形象生成设置">
          <label className="custom-consent"><input type="checkbox" checked={form.autoVideo} disabled={disabled} onChange={event => update('autoVideo', event.target.checked)} /><span><b>同时生成动态形象</b><small>Seedance 2.0 Mini · 480p · 约 10 秒</small></span></label>
          {form.autoVideo ? <>
            {autoVideoAvailable ? <p>创建角色后自动提交 <b>1 次</b>视频任务，预计 <strong>¥{generation.estimatedCostCny!.toFixed(2)}</strong>，从项目已批准额度扣除。无需再次点确认。</p> : <p>{generation?.reason || (listError ? '暂时无法读取视频通道与费用。' : '视频通道或费用暂未就绪。')}本次仍可保存人物卡和照片；未提交的任务不会在后台自动补交。</p>}
            <small>不会自动重试、重复付费或改用其他模型。可先进入剧情，不必等待视频。</small>
          </> : <p>仅创建人物卡，使用你的照片游玩；不会提交视频任务。</p>}
        </section>
        <div className="custom-privacy-note"><b>只属于你的本局</b><p>照片和个人资料不加入公开嘉宾库，也不向其他玩家展示。{providerLabel ? `生成卡片时，填写的信息会发送给当前台词模型 ${providerLabel}。` : '当前未配置台词模型，会直接整理你填写的资料，不会虚构模型生成结果。'}开启“同时生成动态形象”时，点击创建即同意将照片发送给视频服务，并按显示费用提交一次任务。取消勾选则不会发送给视频服务。你可以删除自己的角色及关联记录。</p></div>
        <label className="custom-consent"><input type="checkbox" required checked={form.consent} disabled={disabled} onChange={event => update('consent', event.target.checked)} /><span>我已年满 18 周岁，照片中的成年人是我本人或已获得本人授权；同意按上述用途处理所填写信息与照片。</span></label>
        <button className="primary-button custom-primary" type="submit" disabled={disabled || photoLoading || !form.photoDataUrl || !form.consent || saved.length >= 5}><span>{busy === 'create' ? '正在准备你的人物卡…' : saved.length >= 5 ? '已保存 5 位角色，请先删除一位' : form.autoVideo && autoVideoAvailable ? '生成人物卡并开启动态视频' : '生成人物卡'}</span><Icon name="arrow-right" size={20} /></button>
        <p className="custom-help custom-centered">{form.autoVideo && autoVideoAvailable ? '一次创建，只提交一次视频；旧角色不会自动补单。' : '先以你的照片进入故事，视频未提交不影响开局。'}</p>
      </form>
    </> : profile && <>
      <section className="custom-profile-preview glass-card">
        <div className="custom-profile-identity"><img src={profile.character.portrait} alt={`${profile.character.name}的个人形象`} /><div><span className="custom-eyebrow">我的角色 · {profile.character.mbti}</span><h2>{profile.character.name}</h2><p>{profile.character.occupation || '从你愿意分享的生活开始'}</p></div></div>
        <div className="custom-card-dialogue"><span>你的开场白</span><p>{profile.cardPreview.introduction}</p></div>
        {profile.cardPreview.source === 'user-profile' && <p className="custom-help">根据你填写的资料整理；未使用模型补写。进入故事后，对白仍会参考这张人物卡。</p>}
        <dl className="custom-card-details"><div><dt>表达方式</dt><dd>{profile.cardPreview.voice}</dd></div><div><dt>相处偏好</dt><dd>{profile.cardPreview.preferences || '从聊天里慢慢了解，不预设你的喜好。'}</dd></div><div><dt>尊重边界</dt><dd>{profile.cardPreview.boundary || '相处节奏由你决定；不强迫表态，身体接触前先征求同意。'}</dd></div></dl>
        <button className="primary-button custom-primary" type="button" disabled={disabled} onClick={() => { setAttemptedStartId(profile.id); onStart(profile) }}><span>{starting ? '正在为你开启故事…' : `以${profile.character.name}的身份进入小屋`}</span><Icon name="arrow-right" size={20} /></button>
        <p className="custom-help custom-centered">{videoReady ? '将使用你已确认的动态形象。' : '现在即可使用你的照片游玩，不必等待视频。'} 剧情选择由你决定。</p>
        {startError && attemptedStartId === profile.id && <p className="custom-feedback custom-feedback--error" role="alert">{startError}</p>}
      </section>

      <section className="custom-video-panel glass-card" aria-label="专属动态形象">
        <div className="custom-section-title"><h2>让你的形象动起来</h2><span className="custom-video-badge">{videoReady ? '已确认' : candidate ? '待你确认' : processing ? '生成中' : !profile.generation.available || profile.generation.estimatedCostCny == null ? '暂未启用' : profile.video.status !== 'planned' ? '需检查' : '可生成'}</span></div>
        <p>以你的照片为参考，生成约 {videoDuration} 秒、{videoResolution} 的写实动态肖像。不会借用其他嘉宾的脸，也不会代你说出未确认的话。</p>
        <p className="custom-help">{profile.video.usedModel ? '实际返回模型' : '请求模型'}：{modelName(videoModel)}{profile.video.usedModel && profile.video.requestedModel && profile.video.usedModel !== profile.video.requestedModel ? `；原请求：${modelName(profile.video.requestedModel)}` : ' · 不自动切换其他模型'}</p>
        {(candidate || videoReady) && profile.video.videoUrl && <CustomVideoPreview key={profile.video.videoUrl} src={profile.video.videoUrl} poster={profile.character.portrait} />}
        {profile.video.message && <p className="custom-feedback" role="status">{profile.video.message}</p>}
        {processing ? <div className="custom-feedback" role="status"><p>{profile.video.status === 'reserved' ? '已安排一次生成任务，正在提交。' : '视频任务正在排队或生成。'}可以先进入故事；稍后回到这里查看，不会自动重新付费生成。</p><button className="custom-text-button" type="button" onClick={refreshProfile} disabled={disabled}>检查生成状态</button></div>
          : candidate ? <><p className="custom-help">请确认脸部像你、动作自然、没有错脸或变形后，再用于游戏。不满意可以保留照片游玩。</p><button className="custom-secondary-button" type="button" disabled={disabled || !profile.video.videoUrl} onClick={approveVideo}>{busy === 'approve' ? '正在保存确认…' : '形象符合预期，使用这个视频'}</button></>
            : videoReady ? <p className="custom-help">动态形象已确认。下次以此角色开局时会自动使用。</p>
              : profile.generation.available && profile.generation.estimatedCostCny != null ? <div className="custom-video-cost"><p>预计新增费用 <strong>¥{profile.generation.estimatedCostCny.toFixed(2)}</strong> · 从项目已批准额度扣除</p><button className="custom-secondary-button" type="button" disabled={disabled || profile.video.status !== 'planned'} onClick={startVideo}>{busy === 'video' ? '正在提交一次生成…' : profile.video.status !== 'planned' ? '上次生成需要检查，暂不重复付费' : `提交 ${profile.generation.durationSeconds || 10} 秒动态视频 · ¥${profile.generation.estimatedCostCny.toFixed(2)}`}</button><small>仅补交尚未提交的任务。失败或状态不确定时，不会自动重试或换模型。</small></div>
                : <div className="custom-video-cost"><p className="custom-feedback" id="custom-video-unavailable-reason">{profile.generation.reason || '动态视频通道或预算尚未开放。你的人物卡和照片已经可以正常游玩。'}</p><button className="custom-secondary-button" type="button" disabled aria-describedby="custom-video-unavailable-reason">动态视频暂未启用</button><button className="custom-text-button" type="button" onClick={refreshProfile} disabled={disabled}>{busy === 'status' ? '正在检查视频通道…' : '重新检查视频通道（不扣费）'}</button><small>仅更新通道和费用信息，不提交生成任务、不清空人物卡。通道恢复后，你可以选择提交一次。</small></div>}
        {statusError && <div className="custom-feedback custom-feedback--error" role="alert"><p>状态暂时没有读取成功：{statusError}</p><button className="custom-text-button" type="button" onClick={refreshProfile} disabled={disabled}>重新检查状态（不重新生成）</button></div>}
      </section>
      <div className="custom-profile-actions"><button className="custom-text-button" type="button" disabled={disabled} onClick={() => { setStep('form'); setError(''); setDeleteConfirmation(false) }}>返回我的角色与创建表单</button><button className="custom-text-button custom-danger" type="button" disabled={disabled} onClick={() => setDeleteConfirmation(true)}>删除这个角色</button></div>
      {deleteConfirmation && <section className="custom-delete-confirmation" role="alertdialog" aria-labelledby="custom-delete-title"><h2 id="custom-delete-title">确认删除 {profile.character.name}？</h2><p>本项目存储的人物卡、照片、动态视频及关联游戏记录将被删除，无法恢复。如曾提交视频生成，此操作不会代你删除生成服务方已接收的素材。</p><div><button className="custom-secondary-button" type="button" disabled={disabled} onClick={() => setDeleteConfirmation(false)}>保留角色</button><button className="custom-secondary-button custom-danger" type="button" disabled={disabled} onClick={deleteProfile}>{busy === 'delete' ? '正在删除…' : '确认删除'}</button></div></section>}
    </>}
    <footer className="custom-character-footer">人物卡是故事中的你，不是对真实人格的判断。你始终可以选择、拒绝，或重新开始。</footer>
  </main>
}
