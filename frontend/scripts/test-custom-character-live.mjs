// Real PostgreSQL + HTTP + browser flow, refused outside a credential-free QA schema.
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { mkdirSync, writeFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import assert from 'node:assert/strict'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright')
const baseUrl = process.env.CUSTOM_UI_BASE_URL || 'http://127.0.0.1:4186'
const output = process.env.CUSTOM_UI_QA_DIR || '/tmp/heart-journey-custom-live'
const health = await fetch(`${baseUrl}/health`).then(response => response.json())
assert.equal(health.databaseSchema, 'custom_player_browser_qa_r11', 'Never run destructive QA on a user runtime schema')
assert.deepEqual(health.llmProviders.available, [], 'No paid text model may be enabled in this test')
mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_BROWSER_CHANNEL ? { channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL } : {}) })
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
const clientId = randomUUID()
await context.addInitScript(id => {
  localStorage.setItem('heart-journey-public-client-id', id)
  localStorage.setItem('heart-journey-llm-provider', 'deepseek') // stale selection must not force an unavailable provider.
}, clientId)
const page = await context.newPage()
page.setDefaultTimeout(20_000)
const errors = []
page.on('pageerror', error => errors.push(error.message))
let customId = ''
let photoUrl = ''
let runId = ''
let unavailableModelVerified = false
try {
  await page.goto(`${baseUrl}/?intro=1`)
  await page.getByRole('button', { name: '创建我的角色', exact: false }).click()
  await page.getByLabel('昵称', { exact: true }).fill('QA南星')
  await page.getByLabel('年龄', { exact: true }).fill('26')
  await page.getByLabel('我的 MBTI').selectOption('ISTP')
  await page.getByLabel('角色性别').selectOption('female')
  await page.getByLabel('职业 / 目前在做什么', { exact: true }).fill('建筑设计师')
  await page.getByLabel('想让嘉宾先认识你的哪一面？', { exact: false }).fill('慢热，喜欢周末徒步，来这里想认识能一起做饭的人。')
  await page.getByLabel('喜欢怎样的相处？', { exact: true }).fill('喜欢轻松的玩笑和一起做饭。')
  await page.getByLabel('不喜欢什么？有什么要尊重的边界？', { exact: true }).fill('不催我表态，身体接触前先询问。')
  await page.getByLabel('上传个人形象照').setInputFiles(fileURLToPath(new URL('../public/media/portraits/qiaolan.jpg', import.meta.url)))
  await page.getByAltText('你上传的形象预览').waitFor()
  // Even if a developer misconfigures this QA server, the live browser test
  // explicitly opts out: only the isolated mocked test covers paid submission.
  await page.getByRole('checkbox', { name: /同时生成动态形象/ }).uncheck()
  await page.getByRole('checkbox', { name: /我已年满 18 周岁/ }).check()
  const createResponsePromise = page.waitForResponse(response => response.url().endsWith('/api/custom-characters') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '生成人物卡', exact: true }).click()
  const createResponse = await createResponsePromise
  assert.equal(createResponse.status(), 201)
  assert.equal(createResponse.request().postDataJSON().autoVideo, false)
  assert.equal(createResponse.request().headers()['x-llm-provider'], undefined, 'Unavailable stored model is not forced in request headers')
  const profile = await createResponse.json()
  customId = profile.id
  photoUrl = profile.character.portrait
  assert.equal(profile.generation.available, false)
  assert.equal(profile.cardPreview.source, 'user-profile')
  assert.ok(profile.cardPreview.introduction.includes('QA南星'))
  await page.getByRole('heading', { name: '这次，以你的模样登场。' }).waitFor()
  await page.getByAltText('QA南星的个人形象').evaluate(async image => {
    await image.decode()
    if (image.naturalWidth < 128) throw new Error('Normalized real photograph did not load')
  })
  for (const height of [844, 720, 620]) {
    await page.setViewportSize({ width: 390, height })
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: `${output}/profile-390x${height}.png` })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  }

  const startResponsePromise = page.waitForResponse(response => response.url().endsWith('/api/runs') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '以QA南星的身份进入小屋' }).click()
  const startResponse = await startResponsePromise
  assert.ok([200, 201].includes(startResponse.status()))
  const view = await startResponse.json()
  runId = view.snapshot.runId
  assert.equal(view.snapshot.player.customCharacterId, customId)
  assert.equal(view.snapshot.player.displayName, 'QA南星')
  assert.equal(view.characters.length, 8)
  assert.equal(view.characters.filter(character => character.isCustom).length, 1)
  await page.locator('.game-shell').waitFor()
  const self = page.getByRole('button', { name: 'QA南星，你的当前视角，不可与自己私聊', exact: true })
  assert.equal(await self.isDisabled(), true)
  const ownStagePhoto = page.locator('.scene-stage .scene-media__poster')
  assert.equal(await ownStagePhoto.getAttribute('src'), photoUrl, 'Own uploaded face is used, not a guest identity fallback')
  await page.screenshot({ path: `${output}/game-390x620.png` })

  const npc = page.locator('.dock-avatar:not([disabled])').first()
  await npc.click()
  await page.getByRole('dialog').waitFor()
  await page.getByPlaceholder(/^只对.+说…$/).fill('你好，我叫QA南星，喜欢徒步。有机会我们一起走走吧。')
  const messageResponsePromise = page.waitForResponse(response => /\/agents\/[^/]+\/messages$/.test(new URL(response.url()).pathname) && response.request().method() === 'POST')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  const messageResponse = await messageResponsePromise
  assert.equal(messageResponse.status(), 503, 'Unconfigured model is reported honestly, never disguised as a model reply')
  const chat = await messageResponse.json()
  assert.equal(typeof chat.detail, 'string')
  unavailableModelVerified = true
  await page.getByRole('button', { name: '关闭私聊', exact: true }).click()

  await page.goto(baseUrl)
  await page.locator('.game-shell').waitFor()
  assert.equal(await page.getByRole('button', { name: 'QA南星，你的当前视角，不可与自己私聊', exact: true }).isDisabled(), true)
  await page.goto(`${baseUrl}/?intro=1`)
  await page.getByRole('button', { name: '创建我的角色', exact: false }).click()
  await page.getByRole('button', { name: /QA南星 ISTP/ }).click()
  await page.getByRole('button', { name: '删除这个角色', exact: true }).click()
  await page.getByRole('button', { name: '确认删除', exact: true }).click()
  await page.getByRole('heading', { name: '把你自己，带进故事里。' }).waitFor()
  const deletedPhoto = await context.request.get(`${baseUrl}${photoUrl}`)
  assert.ok([404, 410].includes(deletedPhoto.status()), 'Deletion revokes the opaque media capability')
  const bootstrap = await context.request.get(`${baseUrl}/api/bootstrap`, { headers: { 'X-Client-Id': clientId } }).then(response => response.json())
  assert.equal(bootstrap.view, null, 'Deleting custom profile removes its linked game and memories')
  assert.deepEqual(errors, [])
  const report = { result: 'passed', mode: 'real local PostgreSQL and HTTP, all paid providers disabled; live LLM and video generation not tested', schema: health.databaseSchema, contentVersion: health.contentVersion, viewports: ['390x844', '390x720', '390x620'], checks: ['real photo upload and normalized asset delivery', 'unavailable model does not force invalid header', 'transparent deterministic card', 'custom run with 7 NPCs', 'correct own-photo stage fallback', 'no self chat', 'honest model unavailable response', 'reload custom run', 'saved profile reopen', 'deletion of linked run and media revocation', 'no horizontal overflow'], unavailableModelVerified, pageErrors: errors }
  writeFileSync(`${output}/report.json`, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} catch (error) {
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw error
} finally {
  if (customId) await context.request.delete(`${baseUrl}/api/custom-characters/${customId}`, { headers: { 'X-Client-Id': clientId } }).catch(() => {})
  await browser.close()
}
