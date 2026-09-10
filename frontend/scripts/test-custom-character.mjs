// No live model or paid media calls: UI contract and request-safety regression.
// Run with a local Vite server and PLAYWRIGHT_PACKAGE when it is not installed.
import { createRequire } from 'node:module'
import assert from 'node:assert/strict'
import { mkdirSync, writeFileSync } from 'node:fs'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright')
const baseUrl = process.env.CUSTOM_UI_BASE_URL || 'http://127.0.0.1:5194'
const output = process.env.CUSTOM_UI_QA_DIR || '/tmp/heart-journey-custom-ui'
mkdirSync(output, { recursive: true })

const photo = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOioAAAAASUVORK5CYII='
const profile = {
  id: 'custom-test-only',
  character: { id: 'custom-test-only', name: '南星', mbti: 'ISTP', gender: '女性', portrait: photo, occupation: '建筑设计师', isCustom: true },
  cardPreview: { introduction: '大家好，我叫南星，是建筑设计师。周末喜欢徒步，有机会可以一起出去走走。', voice: '直接、自然，不用刻意热络。', preferences: '喜欢徒步、一起做饭和轻松的玩笑。', boundary: '不催我表态，身体接触前先询问。', source: 'user-profile' },
  video: { status: 'planned', message: '可以先用照片进入故事。' },
  generation: { available: true, estimatedCostCny: 3.25, durationSeconds: 10, resolution: '480p', modelLabel: 'Seedance 2.0 Mini', autoSubmit: true },
}
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_BROWSER_CHANNEL ? { channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL } : {}) })
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
const page = await context.newPage()
page.setDefaultTimeout(10_000)
const errors = []
page.on('pageerror', error => errors.push(error.message))
let stored = []
let createCalls = []
let videoCalls = []
let startCalls = []
let createShouldFail = true
let createDelay = 0
let automaticVideoSubmissions = 0
let generation = structuredClone(profile.generation)
await page.route('**/api/**', async route => {
  const request = route.request()
  const path = new URL(request.url()).pathname
  const data = request.postDataJSON()
  const json = (payload, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(payload) })
  if (path === '/api/bootstrap') return json({ characters: [], view: null, llmProviders: { available: ['deepseek'], default: 'deepseek' } })
  if (path === '/api/custom-characters' && request.method() === 'GET') return json({ characters: stored, generation })
  if (path === '/api/custom-characters' && request.method() === 'POST') {
    createCalls.push(data)
    if (createDelay) await new Promise(resolve => setTimeout(resolve, createDelay))
    if (createShouldFail) { createShouldFail = false; return json({ detail: '测试连接中断，人物卡尚未写入。' }, 503) }
    stored = [structuredClone(profile)]
    stored[0].generation = structuredClone(generation)
    if (data.autoVideo && generation.available && data.maxCostCny != null) {
      automaticVideoSubmissions += 1
      stored[0].video = { status: 'reserved', message: '已预留一次额度，待提交。' }
    } else if (data.autoVideo) {
      stored[0].video.message = '视频未提交：项目预算暂不可用。照片和人物卡已保存。'
    }
    return json(stored[0])
  }
  if (path.endsWith('/video/approve')) {
    stored[0].video.status = 'approved'
    stored[0].video.message = '已确认用于游戏。'
    return json(stored[0])
  }
  if (path.endsWith('/video')) {
    videoCalls.push(data)
    stored[0].video = { status: 'processing', message: '视频生成中。' }
    return json(stored[0])
  }
  if (path === '/api/custom-characters/custom-test-only') {
    if (request.method() === 'DELETE') { stored = []; return json({ deleted: true }) }
    stored[0].generation = structuredClone(generation)
    if (['reserved', 'processing'].includes(stored[0].video.status)) stored[0].video = { status: 'candidate', videoUrl: '/media/video/E01-arrival-reveal.mp4', message: '请确认形象后使用。' }
    return json(stored[0])
  }
  if (path === '/api/runs') { startCalls.push(data); return json({ detail: '测试开局服务暂忙，可重试，人物卡已保留。' }, 503) }
  return json({ detail: 'Unexpected mocked route' }, 404)
})

try {
  await page.goto(`${baseUrl}/?intro=1`)
  await page.getByRole('button', { name: '创建我的角色', exact: false }).click()
  await page.getByRole('heading', { name: '把你自己，带进故事里。' }).waitFor()
  const autoVideoToggle = page.getByRole('checkbox', { name: /同时生成动态形象/ })
  const consent = page.getByRole('checkbox', { name: /我已年满 18 周岁/ })
  const createButton = () => page.getByRole('button', { name: /^(生成人物卡|生成人物卡并开启动态视频)$/ })
  assert.equal(await autoVideoToggle.isChecked(), true, 'Video is opted in by default, with disclosed quote')
  await page.getByText('Seedance 2.0 Mini · 480p · 约 10 秒', { exact: true }).waitFor()
  await page.getByText('无需再次点确认。', { exact: false }).waitFor()
  assert.equal(await page.getByLabel('我的 MBTI').locator('option').count(), 16)
  await page.getByLabel('昵称', { exact: true }).fill('南星')
  await page.getByRole('button', { name: '返回选择', exact: true }).click()
  await page.getByRole('button', { name: '创建我的角色', exact: false }).click()
  assert.equal(await page.getByLabel('昵称', { exact: true }).inputValue(), '南星', 'Closing preserves in-memory draft')
  await page.getByLabel('年龄', { exact: true }).fill('26')
  await page.getByLabel('我的 MBTI').selectOption('ISTP')
  await page.getByLabel('角色性别').selectOption('female')
  await page.getByLabel('职业 / 目前在做什么', { exact: true }).fill('建筑设计师')
  await page.getByLabel('想让嘉宾先认识你的哪一面？', { exact: false }).fill('慢热，喜欢徒步。')
  await page.getByLabel('喜欢怎样的相处？', { exact: true }).fill('一起做饭和轻松的玩笑。')
  await page.getByLabel('不喜欢什么？有什么要尊重的边界？', { exact: true }).fill('不催我表态，身体接触前先询问。')
  await page.getByLabel('上传个人形象照').setInputFiles({ name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('not a photo') })
  await page.getByRole('alert').filter({ hasText: '请选择 JPG' }).waitFor()
  await page.getByLabel('上传个人形象照').setInputFiles({ name: 'own-photo.png', mimeType: 'image/png', buffer: Buffer.from(photo.split(',')[1], 'base64') })
  await page.getByAltText('你上传的形象预览').waitFor()
  assert.equal(await createButton().isDisabled(), true)
  await consent.check()
  await page.getByLabel('年龄', { exact: true }).fill('17')
  await createButton().click()
  assert.equal(createCalls.length, 0, 'Underage form cannot submit')
  await page.getByLabel('年龄', { exact: true }).fill('26')
  await page.locator('.custom-video-option').scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/automatic-video-disclosure-390x844.png`, fullPage: false })
  for (const height of [844, 720, 620]) {
    await page.setViewportSize({ width: 390, height })
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: `${output}/form-390x${height}.png`, fullPage: false })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Form has no horizontal overflow at 390x${height}`)
  }
  await createButton().click()
  await page.getByRole('alert').filter({ hasText: '测试连接中断' }).waitFor()
  await createButton().click()
  await page.getByRole('heading', { name: '这次，以你的模样登场。' }).waitFor()
  assert.equal(createCalls.length, 2)
  assert.equal(createCalls[0].requestId, createCalls[1].requestId, 'Retry must preserve idempotency request ID')
  assert.equal(createCalls[1].age, 26)
  assert.equal(createCalls[1].autoVideo, true, 'Create authorizes one default automatic video')
  assert.equal(createCalls[1].maxCostCny, 3.25, 'Automatic generation is bounded by the displayed quote')
  assert.equal(automaticVideoSubmissions, 1)
  await page.getByText('已安排一次生成任务，正在提交。', { exact: false }).waitFor()
  assert.equal(videoCalls.length, 0, 'Frontend never separately submits a second video for automatic creation')
  assert.equal(await page.evaluate(() => JSON.stringify(localStorage).includes('南星')), false, 'Private profile is not persisted in browser storage')

  for (const height of [844, 720, 620]) {
    await page.setViewportSize({ width: 390, height })
    await page.screenshot({ path: `${output}/preview-390x${height}.png`, fullPage: false })
    const geometry = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, smallButtons: [...document.querySelectorAll('.custom-character-page button')].filter(button => button.getBoundingClientRect().height < 44).map(button => button.textContent) }))
    assert.ok(geometry.document <= geometry.viewport, `No horizontal overflow at 390x${height}`)
    assert.deepEqual(geometry.smallButtons, [], `44px tap targets at 390x${height}`)
  }
  await page.getByRole('button', { name: '以南星的身份进入小屋' }).click()
  await page.getByRole('alert').filter({ hasText: '测试开局服务暂忙' }).waitFor()
  assert.deepEqual(startCalls[0], { mbti: 'ISTP', customCharacterId: 'custom-test-only' })
  if (await page.getByRole('button', { name: '检查生成状态', exact: true }).count()) await page.getByRole('button', { name: '检查生成状态', exact: true }).click()
  await page.getByRole('button', { name: '形象符合预期，使用这个视频' }).waitFor()
  assert.equal(videoCalls.length, 0, 'Polling does not resubmit generation')
  const inlineVideo = page.locator('.custom-video-preview')
  await inlineVideo.scrollIntoViewIfNeeded()
  const paint = await inlineVideo.evaluate(async video => {
    const filteredAncestors = []
    for (let node = video.parentElement; node; node = node.parentElement) {
      const style = getComputedStyle(node)
      if (style.backdropFilter && style.backdropFilter !== 'none') filteredAncestors.push(node.className)
    }
    video.muted = true
    await video.play()
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('No decoded video frame')), 8000)
      video.requestVideoFrameCallback(() => { clearTimeout(timeout); resolve() })
    })
    video.pause()
    const canvas = document.createElement('canvas')
    canvas.width = 32; canvas.height = 32
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, 32, 32)
    const pixels = ctx.getImageData(0, 0, 32, 32).data
    let visiblePixels = 0
    for (let i = 0; i < pixels.length; i += 4) if (pixels[i] + pixels[i + 1] + pixels[i + 2] > 45) visiblePixels += 1
    return { filteredAncestors, width: video.videoWidth, height: video.videoHeight, visiblePixels }
  })
  assert.deepEqual(paint.filteredAncestors, [], 'Inline video must not inherit backdrop-filter compositing')
  assert.ok(paint.width > 0 && paint.height > 0 && paint.visiblePixels > 100, 'Video has a real decoded, non-black frame, not just a moving progress bar')
  for (const viewport of [{ width: 390, height: 844 }, { width: 390, height: 720 }, { width: 390, height: 620 }, { width: 1280, height: 800 }]) {
    await page.setViewportSize(viewport)
    await page.getByRole('button', { name: '放大查看完整视频' }).click()
    const viewer = page.getByRole('dialog', { name: '完整动态形象预览' })
    await viewer.waitFor()
    const layout = await viewer.evaluate(element => {
      const video = element.querySelector('video')
      const rect = video.getBoundingClientRect()
      const close = element.querySelector('button').getBoundingClientRect()
      return { fit: getComputedStyle(video).objectFit, bounds: rect.top >= 0 && rect.bottom <= innerHeight && rect.left >= 0 && rect.right <= innerWidth,
        closeVisible: close.top >= 0 && close.bottom <= innerHeight, src: video.getAttribute('src'), inlinePaused: document.querySelector('.custom-video-preview').paused }
    })
    assert.equal(layout.fit, 'contain')
    assert.equal(layout.bounds, true, `Complete frame visible at ${viewport.width}x${viewport.height}`)
    assert.equal(layout.closeVisible, true)
    assert.equal(layout.inlinePaused, true, 'Only enlarged player can own playback')
    assert.equal(layout.src, await page.locator('.custom-video-preview').getAttribute('src'), 'Viewer reuses the existing asset')
    if (viewport.height === 620) await page.screenshot({ path: `${output}/complete-video-390x620.png` })
    await page.keyboard.press('Escape')
    await viewer.waitFor({ state: 'hidden' })
    assert.equal(await page.locator('.custom-video-dialog video').evaluate(video => video.paused), true)
  }
  assert.equal(videoCalls.length, 0, 'Enlarging and closing never submit a generation')
  await page.setViewportSize({ width: 390, height: 620 })
  await page.getByRole('button', { name: '形象符合预期，使用这个视频' }).click()
  await page.getByText('将使用你已确认的动态形象。', { exact: false }).waitFor()
  stored[0].video.durationSeconds = 5
  stored[0].video.requestedModel = 'seedance-2.0'
  stored[0].video.usedModel = 'seedance-2.0'
  await page.getByRole('button', { name: '返回我的角色与创建表单' }).click()
  const savedRefresh = page.waitForResponse(response => response.url().endsWith('/api/custom-characters') && response.request().method() === 'GET')
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await savedRefresh
  await page.getByRole('button', { name: /南星 ISTP/ }).click()
  await page.getByText('生成约 5 秒、480p', { exact: false }).waitFor()
  await page.getByText('实际返回模型：Seedance 2.0 · 不自动切换其他模型', { exact: true }).waitFor()
  assert.equal(automaticVideoSubmissions, 1, 'Reopening an old card does not automatically submit')
  assert.equal(videoCalls.length, 0)
  await page.getByRole('button', { name: '删除这个角色', exact: true }).click()
  await page.getByRole('alertdialog').waitFor()
  await page.getByRole('button', { name: '保留角色', exact: true }).click()
  assert.equal(stored.length, 1)
  await page.getByRole('button', { name: '删除这个角色', exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  await page.getByRole('heading', { name: '把你自己，带进故事里。' }).waitFor()
  assert.equal(stored.length, 0)

  // Submitting a new draft after changing it gets a new idempotency key.
  await page.getByLabel('昵称', { exact: true }).fill('南星二')
  await autoVideoToggle.uncheck()
  await page.getByLabel('上传个人形象照').setInputFiles({ name: 'own-photo.png', mimeType: 'image/png', buffer: Buffer.from(photo.split(',')[1], 'base64') })
  createDelay = 300
  await createButton().dblclick()
  await page.getByRole('heading', { name: '这次，以你的模样登场。' }).waitFor()
  assert.equal(createCalls.length, 3, 'Double click submits only once')
  assert.notEqual(createCalls[1].requestId, createCalls[2].requestId, 'Edited draft gets a new idempotency key')
  assert.equal(createCalls[2].autoVideo, false)
  assert.equal(createCalls[2].maxCostCny, null)
  assert.equal(automaticVideoSubmissions, 1, 'Opting out creates no video task')
  await page.getByRole('button', { name: '提交 10 秒动态视频 · ¥3.25' }).click()
  assert.deepEqual(videoCalls, [{ confirmed: true, maxCostCny: 3.25 }], 'Planned-only manual submission retains explicit price ceiling')
  await page.getByRole('button', { name: '删除这个角色', exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  generation = { ...generation, available: false, estimatedCostCny: null, reason: '项目预算暂不可用。' }
  await page.getByRole('button', { name: '返回选择', exact: true }).click()
  await page.getByRole('button', { name: '创建我的角色', exact: false }).click()
  await autoVideoToggle.check()
  await page.getByText('项目预算暂不可用。', { exact: false }).waitFor()
  await page.getByLabel('昵称', { exact: true }).fill('南星三')
  await page.getByLabel('上传个人形象照').setInputFiles({ name: 'own-photo.png', mimeType: 'image/png', buffer: Buffer.from(photo.split(',')[1], 'base64') })
  await createButton().click()
  await page.getByRole('heading', { name: '这次，以你的模样登场。' }).waitFor()
  assert.equal(createCalls[3].autoVideo, true)
  assert.equal(createCalls[3].maxCostCny, null, 'Unavailable quote cannot authorize spend')
  assert.equal(automaticVideoSubmissions, 1, 'Unavailable budget keeps card and photograph without generation')
  await page.getByText('视频未提交：项目预算暂不可用。照片和人物卡已保存。', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: '以南星的身份进入小屋' }).isEnabled(), true, 'Video unavailability never blocks story entry')
  await page.locator('.custom-video-badge').filter({ hasText: '暂未启用' }).waitFor()
  assert.equal(await page.getByRole('button', { name: '动态视频暂未启用', exact: true }).isDisabled(), true, 'Unavailable channel has an explicit disabled generation control')
  await page.locator('.custom-video-panel').scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/video-channel-unavailable-390x620.png`, fullPage: false })
  const beforeChannelRefresh = { videos: videoCalls.length, creates: createCalls.length }
  await page.getByRole('button', { name: '重新检查视频通道（不扣费）', exact: true }).click()
  await page.getByRole('button', { name: '重新检查视频通道（不扣费）', exact: true }).waitFor()
  assert.equal(videoCalls.length, beforeChannelRefresh.videos)
  assert.equal(createCalls.length, beforeChannelRefresh.creates)
  generation = { ...generation, available: true, estimatedCostCny: 3.25, reason: '' }
  await page.getByRole('button', { name: '重新检查视频通道（不扣费）', exact: true }).click()
  await page.getByRole('button', { name: '提交 10 秒动态视频 · ¥3.25' }).waitFor()
  assert.equal(videoCalls.length, beforeChannelRefresh.videos, 'Configuration recovery never silently submits video')
  assert.equal(createCalls.length, beforeChannelRefresh.creates, 'Read-only refresh preserves the existing character')
  await page.getByRole('heading', { name: '南星', exact: true }).waitFor()
  await page.getByRole('button', { name: '提交 10 秒动态视频 · ¥3.25' }).click()
  assert.equal(videoCalls.length, beforeChannelRefresh.videos + 1, 'Restored planned task needs one explicit manual submit')
  assert.deepEqual(videoCalls.at(-1), { confirmed: true, maxCostCny: 3.25 })
  stored[0].video.status = 'failed'
  await page.getByRole('button', { name: '检查生成状态', exact: true }).click()
  assert.equal(await page.getByRole('button', { name: '上次生成需要检查，暂不重复付费', exact: true }).isDisabled(), true, 'Failed tasks remain blocked even after channel recovery')
  assert.deepEqual(errors, [])
  const report = { result: 'passed', mode: 'mocked API; no real or paid generation', viewports: ['390x844', '390x720', '390x620'], assertions: ['16 MBTI choices', 'photo format validation', 'consent required', 'underage blocked', 'in-memory draft preserved', 'same-key create retry', 'custom start payload', 'default one automatic video via create only', 'Seedance 2.0 Mini 480p 10-second disclosure', 'quoted cost bound', 'no resubmit on old-card reopen or polling', 'historical video duration and actual model retained', 'opt-out creates photo only', 'unavailable budget leaves card playable', 'disabled channel exposes reason and read-only refresh', 'recovered channel requires explicit planned-task submission', 'failed tasks remain blocked after configuration recovery', 'candidate approval', 'deletion confirmation', '44px controls', 'no horizontal overflow', 'private data not in localStorage', 'double-submit guard'], createRequests: createCalls.length, automaticVideoSubmissionsMocked: automaticVideoSubmissions, manualVideoRequestsMocked: videoCalls.length, pageErrors: errors }
  report.viewports.push('1280x800')
  report.assertions.push('full-frame contain preview and reachable close at all sizes', 'Escape closes and pauses enlarged playback', 'enlargement reuses asset and never submits generation')
  report.assertions.push('inline preview has no backdrop-filter ancestors and decodes a non-black frame')
  writeFileSync(`${output}/report.json`, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally { await browser.close() }
