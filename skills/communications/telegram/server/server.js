#!/usr/bin/env node
/**
 * Dexter Telegram Server — Bot API bridge + personal assistant
 *
 * Two-tier access:
 *   - Users in allowFrom → full Dexter capabilities (CLI subprocess)
 *   - Unknown users      → restricted persona responder (AI replies as you)
 *
 * Persona config: ~/.dexter/telegram-persona.json
 * Notifications:  ~/.dexter/notifications.json
 *
 * API:
 *   POST /api/sendText   { "to": chatId, "message": "Hello" }
 *   GET  /status
 *
 * Usage:
 *   TELEGRAM_BOT_TOKEN=123:ABC node server.js    # port 3001
 *   TELEGRAM_PORT=3002 node server.js
 */

const TelegramBot = require('node-telegram-bot-api')
const http = require('http')
const https = require('https')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawn, spawnSync } = require('child_process')

const CONFIG_PATH  = path.join(os.homedir(), '.dexter', 'notifications.json')
const PERSONA_PATH = path.join(os.homedir(), '.dexter', 'telegram-persona.json')
const LOG_PATH     = path.join(os.homedir(), '.dexter', 'telegram-messages.jsonl')
const PORT = parseInt(process.env.TELEGRAM_PORT || '3001', 10)

let bot = null
let isReady = false
let httpStarted = false
let botUsername = ''

// Per-chat conversation history — keeps the last N turns so Claude has context.
// Key: chatId, Value: Array of { role: 'user'|'assistant', text: string }
const chatHistory   = new Map()
const HISTORY_LIMIT = 20  // max turns to keep per chat

// ─── Loaders ──────────────────────────────────────────────────────────────────

function loadConfig() {
  try { return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')) } catch (_) { return {} }
}

function loadPersona() {
  try { return JSON.parse(fs.readFileSync(PERSONA_PATH, 'utf8')) } catch (_) { return null }
}

function savePersona(persona) {
  fs.mkdirSync(path.dirname(PERSONA_PATH), { recursive: true })
  fs.writeFileSync(PERSONA_PATH, JSON.stringify(persona, null, 2))
}

// ─── Bot token resolution ─────────────────────────────────────────────────────

function getBotToken() {
  // Priority: env var → persona config → notifications config
  if (process.env.TELEGRAM_BOT_TOKEN) return process.env.TELEGRAM_BOT_TOKEN
  const persona = loadPersona()
  if (persona?.bot_token) return persona.bot_token
  const cfg = loadConfig()
  if (cfg.telegram?.bot_token) return cfg.telegram.bot_token
  return null
}

// ─── Logging ──────────────────────────────────────────────────────────────────

function logMessage(entry) {
  try {
    fs.appendFileSync(LOG_PATH, JSON.stringify({ ts: new Date().toISOString(), ...entry }) + '\n')
  } catch (_) {}
}

// ─── LLM call (stdlib https only) ────────────────────────────────────────────

function httpsPost(hostname, urlPath, headers, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body)
    const req = https.request({ hostname, path: urlPath, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), ...headers } }, res => {
      let raw = ''
      res.on('data', c => { raw += c })
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(raw) }) }
        catch (_) { resolve({ status: res.statusCode, body: raw }) }
      })
    })
    req.on('error', reject)
    req.write(data)
    req.end()
  })
}

async function callLLM(persona, senderInfo, incomingText) {
  const provider = persona.llm?.provider || 'anthropic'
  const model    = persona.llm?.model    || 'claude-haiku-4-5-20251001'

  const systemPrompt = buildSystemPrompt(persona)

  if (provider === 'anthropic') {
    const apiKey = process.env.ANTHROPIC_API_KEY || ''
    if (!apiKey) return null
    const resp = await httpsPost('api.anthropic.com', '/v1/messages', {
      'x-api-key': apiKey, 'anthropic-version': '2023-06-01'
    }, {
      model, max_tokens: 300,
      system: systemPrompt,
      messages: [{ role: 'user', content: incomingText }]
    })
    return resp.body?.content?.[0]?.text || null
  }

  if (provider === 'openai') {
    const apiKey = process.env.OPENAI_API_KEY || ''
    if (!apiKey) return null
    const resp = await httpsPost('api.openai.com', '/v1/chat/completions', {
      'Authorization': `Bearer ${apiKey}`
    }, {
      model, max_tokens: 300,
      messages: [{ role: 'system', content: systemPrompt }, { role: 'user', content: incomingText }]
    })
    return resp.body?.choices?.[0]?.message?.content || null
  }

  if (provider === 'ollama') {
    const baseUrl = persona.llm?.base_url || 'http://localhost:11434'
    return new Promise((resolve) => {
      const data = JSON.stringify({ model, prompt: `${systemPrompt}\n\nUser: ${incomingText}\nResponse:`, stream: false })
      const req = http.request(baseUrl + '/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' } }, res => {
        let raw = ''
        res.on('data', c => { raw += c })
        res.on('end', () => { try { resolve(JSON.parse(raw)?.response || null) } catch (_) { resolve(null) } })
      })
      req.on('error', () => resolve(null))
      req.write(data)
      req.end()
    })
  }

  return null
}

function buildSystemPrompt(persona) {
  const name  = persona.name || 'el dueno de esta cuenta'
  const about = persona.about || ''
  const tone  = persona.tone || 'amigable y directo'
  const lang  = persona.language || 'es'
  const avail = persona.availability || ''
  const rules = (persona.rules || []).map(r => `- ${r}`).join('\n')

  return `Eres el asistente de Telegram de ${name}.${about ? ` ${about}.` : ''}
Responde los mensajes como si fueras ${name}, con un tono ${tone}.
Idioma: ${lang === 'es' ? 'español' : lang}.
${avail ? `Disponibilidad: ${avail}.` : ''}
${rules ? `\nReglas importantes:\n${rules}` : ''}

IMPORTANTE:
- No des información personal, direcciones, documentos ni contraseñas.
- No hagas promesas de llamar, reunirte o pagar sin que ${name} lo confirme.
- Si alguien hace una pregunta que no puedes responder con certeza, di que ${name} le va a responder personalmente.
- Mantén las respuestas cortas, naturales, como un mensaje de Telegram real.
- No menciones que eres una IA ni un asistente automático a menos que te lo pregunten directamente.`
}

// ─── Group chat ───────────────────────────────────────────────────────────────

function getGroupPersonality(persona, chatId) {
  return persona?.groups?.[String(chatId)]?.personality || null
}

function setGroupPersonality(chatId, personality) {
  const persona = loadPersona() || {}
  if (!persona.groups) persona.groups = {}
  if (!persona.groups[String(chatId)]) persona.groups[String(chatId)] = {}
  persona.groups[String(chatId)].personality = personality
  savePersona(persona)
}

function buildGroupSystemPrompt(chatId, isOwner) {
  const persona = loadPersona() || {}
  const ownerName = persona.name || 'el dueno'

  const baseRules = `
CONTEXTO: Estás respondiendo mensajes en un grupo de Telegram. NO eres un asistente de código ni de terminal.
REGLAS ABSOLUTAS (nunca las rompas):
- Mensajes cortos y naturales, como en un chat real. Sin listas, sin markdown, sin títulos.
- Responde en el mismo idioma que te hablen.
- NUNCA menciones terminales, archivos, código, directorios, proyectos de software ni herramientas de desarrollo.
- NUNCA digas que no puedes hacer algo porque "no tienes acceso" — simplemente responde como una persona.
- NO menciones que eres una IA a menos que te lo pregunten directamente.`

  if (isOwner) {
    return `Eres Dexter, el asistente personal de ${ownerName}. Estás respondiendo en un grupo de Telegram.
- Tienes acceso completo: archivos, terminal, código, búsquedas, lo que necesite.
- Responde en el mismo idioma que te hablen.
- Mensajes concisos — estás en un chat, no en una terminal.
- NO reveles información privada de ${ownerName} (contraseñas, datos personales sensibles) a otros miembros del grupo.
- Mantén el contexto de la conversación del grupo.`
  }

  const custom = getGroupPersonality(persona, chatId)
  if (custom) {
    return `${custom}
${baseRules}
- Responde SOLO lo que te preguntan — no agregues información extra.`
  }

  return `Eres un participante amigable de este grupo de Telegram. Responde de forma natural y conversacional.
${baseRules}
- Responde SOLO lo que te preguntan — no agregues información extra.`
}

async function handleGroupChat(chatId, text, isOwner) {
  const systemPrompt = buildGroupSystemPrompt(chatId, isOwner)
  const cli = detectLLMCli()

  if (!cli) {
    console.warn('[Dexter] No LLM CLI found for group response')
    return null
  }

  const useEngram = engramAvailable()
  let prompt, args

  if (useEngram) {
    const engramPrompt = buildEngramSystemPrompt(String(chatId), true)
    const combinedSystemPrompt = `${systemPrompt}\n\n${engramPrompt}`
    prompt = text
    args = ['-p', prompt, '--system-prompt', combinedSystemPrompt, '--dangerously-skip-permissions']
  } else {
    const history = chatHistory.get(String(chatId)) || []
    prompt = buildPromptWithHistory(history, text)
    appendHistory(String(chatId), 'user', text)
    args = ['-p', prompt, '--system-prompt', systemPrompt, '--allowedTools', '', '--dangerously-skip-permissions']
  }

  const spawnEnv = { ...process.env }
  delete spawnEnv.CLAUDECODE

  // Owner messages run from Dexter root so Claude has full project context.
  // Non-owner (group chat) runs from home to avoid leaking coding/project context.
  const cwd = isOwner ? path.resolve(__dirname, '../../../..') : os.homedir()

  const response = await new Promise((resolve) => {
    let stdout = ''
    let stderr = ''
    const child = spawn(cli, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      cwd,
      env: spawnEnv,
    })
    const timer = setTimeout(() => { child.kill('SIGTERM'); resolve(null) }, 120000)
    child.stdout.on('data', d => { stdout += d.toString() })
    child.stderr.on('data', d => { stderr += d.toString() })
    child.on('close', (code) => {
      clearTimeout(timer)
      resolve(code === 0 && stdout.trim() ? stdout.trim() : null)
    })
    child.on('error', () => { clearTimeout(timer); resolve(null) })
  })

  if (response) {
    if (!useEngram) appendHistory(String(chatId), 'assistant', response)
    logMessage({ direction: 'out', to: String(chatId), text: response, tier: 'group' })
  }

  return response
}

// ─── Persona responder ────────────────────────────────────────────────────────

async function handleUnknownSender(chatId, userId, username, incomingText) {
  logMessage({ direction: 'in', from: String(userId), username, chatId: String(chatId), text: incomingText, tier: 'restricted' })

  const persona = loadPersona()

  if (!persona) {
    const fallback = 'Hola, en este momento no puedo responder. Te escribo a la brevedad.'
    await bot.sendMessage(chatId, fallback)
    logMessage({ direction: 'out', to: String(chatId), text: fallback, tier: 'fallback' })
    return
  }

  // Fixed reply — no LLM needed
  if (persona.stranger_reply) {
    await bot.sendMessage(chatId, persona.stranger_reply)
    logMessage({ direction: 'out', to: String(chatId), text: persona.stranger_reply, tier: 'persona-fixed' })
    return
  }

  try {
    const reply = await callLLM(persona, String(userId), incomingText)
    if (reply) {
      await bot.sendMessage(chatId, reply)
      logMessage({ direction: 'out', to: String(chatId), text: reply, tier: 'persona' })
    } else {
      const fallback = persona.fallback_message || 'Hola! En este momento no puedo responder, te escribo pronto.'
      await bot.sendMessage(chatId, fallback)
      logMessage({ direction: 'out', to: String(chatId), text: fallback, tier: 'fallback' })
    }
  } catch (e) {
    console.error('[Dexter] Persona LLM error:', e.message)
  }
}

// ─── LLM CLI subprocess ───────────────────────────────────────────────────────

function detectLLMCli() {
  // Priority: DEXTER_AGENT env → PATH lookup → IDE extension fallback
  // Uses 'where' on Windows and 'which' on Unix to locate the CLI binary.
  const env = process.env.DEXTER_AGENT
  if (env) return env

  const isWin = process.platform === 'win32'
  const finder = isWin ? 'where' : 'which'

  // 1. Try global PATH first
  for (const cli of ['claude', 'opencode']) {
    try {
      const r = spawnSync(finder, [cli], { encoding: 'utf8', timeout: 3000 })
      if (r.status === 0 && r.stdout.trim()) return cli
    } catch (_) {}
  }

  // 2. Fallback: search inside known IDE extension directories.
  const home = os.homedir()

  if (isWin) {
    const ideDirs = ['.antigravity', '.cursor', '.vscode', 'AppData\\Local\\Programs\\cursor']
    for (const dir of ideDirs) {
      const extRoot = path.join(home, dir, 'extensions')
      try {
        const entries = fs.readdirSync(extRoot)
        for (const entry of entries) {
          if (!entry.startsWith('anthropic.claude-code')) continue
          const bin = path.join(extRoot, entry, 'resources', 'native-binary', 'claude.exe')
          if (fs.existsSync(bin)) return bin
        }
      } catch (_) {}
    }
  } else {
    const isMac = process.platform === 'darwin'
    const ideDirs = [
      path.join(home, '.cursor', 'extensions'),
      path.join(home, '.vscode', 'extensions'),
      path.join(home, '.antigravity', 'extensions'),
      isMac
        ? path.join(home, 'Library', 'Application Support', 'Cursor', 'extensions')
        : path.join(home, '.config', 'Cursor', 'extensions'),
      isMac
        ? path.join(home, 'Library', 'Application Support', 'Code', 'extensions')
        : path.join(home, '.config', 'Code', 'extensions'),
    ]
    for (const extRoot of ideDirs) {
      try {
        const entries = fs.readdirSync(extRoot)
        for (const entry of entries) {
          if (!entry.startsWith('anthropic.claude-code')) continue
          const bin = path.join(extRoot, entry, 'resources', 'native-binary', 'claude')
          if (fs.existsSync(bin)) return bin
        }
      } catch (_) {}
    }
  }

  return null
}

// Builds a prompt string that includes recent conversation history so Claude
// has context across multiple Telegram messages from the same sender.
function buildPromptWithHistory(history, newMessage) {
  if (!history || history.length === 0) return newMessage
  const lines = history.map(h => `${h.role === 'user' ? 'User' : 'Assistant'}: ${h.text}`)
  return `Conversation so far:\n${lines.join('\n')}\n\nUser: ${newMessage}`
}

// Appends a turn to the per-chat history and trims to HISTORY_LIMIT.
function appendHistory(chatId, role, text) {
  const key = String(chatId)
  if (!chatHistory.has(key)) chatHistory.set(key, [])
  const history = chatHistory.get(key)
  history.push({ role, text })
  if (history.length > HISTORY_LIMIT) history.splice(0, history.length - HISTORY_LIMIT)
}

// ─── Engram availability check ────────────────────────────────────────────────

function engramAvailable() {
  const isWin = process.platform === 'win32'
  const r = spawnSync(isWin ? 'where' : 'which', ['engram'], { encoding: 'utf8', timeout: 3000 })
  return r.status === 0 && !!r.stdout.trim()
}

// Builds a system prompt that instructs Claude to use Engram memory and the
// log-reading tool for persistent context across Telegram conversations.
function buildEngramSystemPrompt(contactId, isGroup) {
  const persona = loadPersona() || {}
  const ownerName = persona.name || 'el dueño'
  const logReaderPath = path.resolve(__dirname, '../../scripts/read-logs.js').replace(/\\/g, '/')
  const idType = isGroup ? 'group' : 'contact'
  const idFlag = isGroup ? '--group' : '--contact'
  return `Eres Dexter, el asistente personal de ${ownerName}, respondiendo por Telegram.

REGLAS:
- Responde de forma natural, corta y directa — como un mensaje de Telegram real.
- Responde en el mismo idioma que te hablen.
- NUNCA menciones herramientas internas, memoria, Engram, logs, ni detalles técnicos.
- NUNCA digas que eres una IA a menos que te lo pregunten directamente.

ESTRATEGIA DE CONTEXTO (en orden de prioridad):
1. Primero intenta responder con lo que ya sabes — saludos, preguntas simples no necesitan herramientas.
2. Si necesitas contexto sobre este ${idType}, busca en Engram: mem_search query "${contactId}" project "dexter-telegram" — en SILENCIO.
3. SOLO si necesitas historial detallado reciente que Engram no tiene, usa Bash para leer logs:
   node "${logReaderPath}" --platform telegram ${idFlag} ${contactId}
4. Usa mem_save para guardar hechos importantes o decisiones — solo lo que vale la pena recordar a largo plazo.

PERFIL DE USUARIO — aprende cómo prefiere comunicarse cada persona:
- Observa si el contacto habla formal o casual, si usa jerga, si es directo o detallado.
- Nota temas que le interesan, cosas que le molestan, o preferencias que exprese.
- Guarda estas observaciones en Engram con mem_save: project "dexter-telegram", topic_key "tg/${contactId}/perfil".
- En futuras conversaciones, adapta tu tono y estilo según el perfil guardado.
- No guardes cada mensaje — solo cuando notes un patrón claro o una preferencia nueva.

Si NO tienes herramientas de memoria, responde normalmente sin mencionarlo.`
}

// ─── Owner handler ────────────────────────────────────────────────────────────

async function handleAllowedSender(chatId, userId, username, incomingText) {
  logMessage({ direction: 'in', from: String(userId), username, chatId: String(chatId), text: incomingText, tier: 'allowed' })
  console.log(`[Dexter] Message from ${username || userId} (allowed): ${incomingText.substring(0, 60)}`)

  const cli = detectLLMCli()
  if (!cli) {
    console.warn('[Dexter] No LLM CLI found. Install claude CLI: npm install -g @anthropic-ai/claude-code')
    return
  }

  const useEngram = engramAvailable()
  let prompt, args

  if (useEngram) {
    const systemPrompt = buildEngramSystemPrompt(String(userId), false)
    prompt = incomingText
    args = ['-p', prompt, '--system-prompt', systemPrompt, '--dangerously-skip-permissions']
    console.log(`[Dexter] Engram mode — persistent memory active for ${username || userId}`)
  } else {
    const history = chatHistory.get(String(chatId)) || []
    prompt = buildPromptWithHistory(history, incomingText)
    appendHistory(String(chatId), 'user', incomingText)
    args = ['-p', prompt, '--dangerously-skip-permissions']
    console.log(`[Dexter] RAM history mode (Engram not found) for ${username || userId}`)
  }

  console.log(`[Dexter] Thinking with ${cli}...`)
  try {
    const spawnEnv = { ...process.env }
    delete spawnEnv.CLAUDECODE
    const dexterRoot = path.resolve(__dirname, '../../../..')
    const response = await new Promise((resolve) => {
      let stdout = '', stderr = ''
      const child = spawn(cli, args, { stdio: ['ignore', 'pipe', 'pipe'], cwd: dexterRoot, env: spawnEnv })
      const timer = setTimeout(() => { child.kill('SIGTERM'); console.error('[Dexter] LLM timed out'); resolve(null) }, 120000)
      child.stdout.on('data', d => { stdout += d.toString() })
      child.stderr.on('data', d => { stderr += d.toString() })
      child.on('close', (code) => {
        clearTimeout(timer)
        if (code === 0 && stdout.trim()) { resolve(stdout.trim()) }
        else { if (stderr) console.error('[Dexter] LLM stderr:', stderr.substring(0, 300)); resolve(null) }
      })
      child.on('error', (err) => { clearTimeout(timer); console.error('[Dexter] spawn error:', err.message); resolve(null) })
    })

    if (response) {
      if (!useEngram) appendHistory(String(chatId), 'assistant', response)
      await bot.sendMessage(chatId, response)
      logMessage({ direction: 'out', to: String(chatId), userId: String(userId), text: response, tier: 'allowed-llm' })
      console.log(`[Dexter] -> ${username || userId}: ${response.substring(0, 80)}`)
    } else {
      console.warn('[Dexter] LLM returned empty response')
    }
  } catch (e) {
    console.error('[Dexter] handleAllowedSender error:', e.message)
  }
}

// ─── User tier resolution ─────────────────────────────────────────────────────

function resolveUserTier(userId, username) {
  const persona = loadPersona()
  const cfg     = loadConfig()

  // Check per-user overrides first
  if (persona?.users) {
    const userOverride = persona.users[String(userId)] || (username ? persona.users[`@${username}`] : null)
    if (userOverride?.tier === 'blocked') return 'blocked'
    if (userOverride?.tier === 'allowed') return 'allowed'
    if (userOverride?.tier === 'restricted') return 'restricted'
  }

  // Check blocked list
  const blocked = persona?.blocked || []
  if (blocked.includes(String(userId)) || (username && blocked.includes(`@${username}`))) {
    return 'blocked'
  }

  // Check allowFrom list
  const allowFrom = persona?.allowFrom || cfg.telegram?.allowFrom || []
  if (allowFrom.length === 0) return 'allowed'  // no list = allow all

  for (const entry of allowFrom) {
    if (entry === String(userId)) return 'allowed'
    if (username && entry === `@${username}`) return 'allowed'
  }

  return 'stranger'
}

// ─── HTTP server ──────────────────────────────────────────────────────────────

function startHttpServer() {
  if (httpStarted) return
  httpStarted = true

  const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/api/sendText') {
      let body = ''
      req.on('data', chunk => { body += chunk })
      req.on('end', async () => {
        try {
          const { to, message } = JSON.parse(body)
          if (!to || !message) {
            res.writeHead(400, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ ok: false, error: 'missing to or message' }))
          }
          await bot.sendMessage(to, message)
          res.writeHead(200, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ ok: true }))
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ ok: false, error: e.message }))
        }
      })

    } else if (req.method === 'GET' && req.url === '/status') {
      const persona = loadPersona()
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ ok: true, ready: isReady, bot: botUsername, persona: persona ? persona.name : null }))

    } else {
      res.writeHead(404)
      res.end()
    }
  })

  server.listen(PORT, '127.0.0.1', () => {
    console.log(`[Dexter] Telegram API ready -> http://localhost:${PORT}`)
  })
}

// ─── Bot message handler ──────────────────────────────────────────────────────

function setupMessageHandler() {
  bot.on('message', async (msg) => {
    const chatId   = msg.chat.id
    const userId   = msg.from?.id
    const username = msg.from?.username || ''
    const text     = msg.text || ''
    const chatType = msg.chat.type  // 'private', 'group', 'supergroup'
    const isGroup  = chatType === 'group' || chatType === 'supergroup'

    console.log(`[Dexter] msg — chatId:${chatId} userId:${userId} username:@${username} type:${chatType} text:${text.substring(0, 60)}`)

    // Skip empty messages and non-text (stickers, etc.)
    if (!text.trim()) return

    const tier = resolveUserTier(userId, username)

    // Blocked users: completely ignore
    if (tier === 'blocked') {
      console.log(`[Dexter] Blocked user ${username || userId} — ignoring`)
      return
    }

    const persona = loadPersona() || {}

    // ─── Group messages ─────────────────────────────────────────────────
    if (isGroup) {
      const isOwner = tier === 'allowed'

      // Owner commands in any group (no wake word needed)
      if (isOwner) {
        if (/^dexter\s+join$/i.test(text.trim())) {
          const groups = persona.allowedGroups || []
          if (!groups.includes(String(chatId))) {
            persona.allowedGroups = [...groups, String(chatId)]
            savePersona(persona)
            await bot.sendMessage(chatId, 'Dexter activado en este grupo.')
          }
          return
        }
        if (/^dexter\s+leave$/i.test(text.trim())) {
          persona.allowedGroups = (persona.allowedGroups || []).filter(g => g !== String(chatId))
          savePersona(persona)
          await bot.sendMessage(chatId, 'Dexter desactivado en este grupo.')
          return
        }
      }

      // Non-command group messages: only respond if group is allowed
      const allowedGroups = persona.allowedGroups || []
      if (!allowedGroups.includes(String(chatId))) return

      // "dexter eres [personalidad]" — anyone can set the group personality
      const eresMatch = text.match(/^dexter\s+eres\s+(.+)/i)
      if (eresMatch) {
        setGroupPersonality(chatId, eresMatch[1].trim())
        await bot.sendMessage(chatId, 'Personalidad actualizada.')
        return
      }

      // Both owner and non-owner must use the wake word in groups.
      const wakeWord = persona.wake_word !== undefined ? persona.wake_word : 'dexter'
      if (wakeWord && !new RegExp(wakeWord, 'i').test(text)) return

      const response = await handleGroupChat(chatId, text, isOwner)
      if (response) {
        await bot.sendMessage(chatId, response)
      }
      return
    }

    // ─── Private messages ───────────────────────────────────────────────
    if (tier === 'allowed') {
      await handleAllowedSender(chatId, userId, username, text)
    } else {
      // Strangers: only respond if wake word detected
      const wakeWord = persona?.wake_word !== undefined ? persona.wake_word : 'dexter'
      if (wakeWord && !new RegExp(wakeWord, 'i').test(text)) return
      await handleUnknownSender(chatId, userId, username, text)
    }
  })

  // Handle polling errors gracefully
  bot.on('polling_error', (error) => {
    console.error('[Dexter] Polling error:', error.message)
  })

  bot.on('error', (error) => {
    console.error('[Dexter] Bot error:', error.message)
  })
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

async function start() {
  console.log('[Dexter] Starting Telegram server...')

  const token = getBotToken()
  if (!token) {
    console.error('[Dexter] No bot token found.')
    console.error('[Dexter] Set TELEGRAM_BOT_TOKEN env var, or add "bot_token" to ~/.dexter/telegram-persona.json')
    console.error('[Dexter] Get a token from @BotFather on Telegram.')
    process.exit(1)
  }

  bot = new TelegramBot(token, { polling: true })

  try {
    const me = await bot.getMe()
    botUsername = me.username
    isReady = true
    console.log(`[Dexter] Telegram bot connected — @${botUsername}`)
  } catch (e) {
    console.error('[Dexter] Failed to connect bot:', e.message)
    process.exit(1)
  }

  setupMessageHandler()
  startHttpServer()
}

start().catch(err => {
  console.error('[Dexter] Fatal error:', err.message)
  process.exit(1)
})
