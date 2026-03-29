#!/usr/bin/env node
/**
 * Dexter WhatsApp Server — Baileys HTTP bridge + personal assistant
 *
 * Two-tier access:
 *   - Numbers in allowFrom → full Dexter capabilities (outbound only, agent handles)
 *   - Unknown numbers     → restricted persona responder (AI replies as you)
 *
 * Pairing: phone number pairing (no QR needed — works headless)
 *   WA_PHONE=+521XXXXXXXXXX node server.js
 *   Or set "allowFrom": ["+52..."] in ~/.dexter/whatsapp-persona.json
 *
 * Persona config: ~/.dexter/whatsapp-persona.json
 * Notifications:  ~/.dexter/notifications.json
 * Credentials:    ~/.dexter/whatsapp/
 *
 * API:
 *   POST /api/sendText   { "to": "+1234567890", "text": "Hello" }
 *   POST /api/sendImage  { "to": "+1234567890", "imageUrl": "https://..." }
 *                        { "to": "+1234567890", "imageBase64": "<b64>", "mimeType": "image/jpeg" }
 *                        optional: "caption": "text"
 *   GET  /status
 *
 * Usage:
 *   WA_PHONE=+521XXXXXXXXXX node server.js    # port 3000
 *   WA_PORT=3001 node server.js
 */

const { default: makeWASocket, DisconnectReason, useMultiFileAuthState, Browsers, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } = require('@whiskeysockets/baileys')
const { Boom } = require('@hapi/boom')
const http = require('http')
const https = require('https')
const fs = require('fs')
const os = require('os')
const path = require('path')
const readline = require('readline')
const { spawn, spawnSync } = require('child_process')

// Prevent Windows spawn errors (AssignProcessToJobObject etc.) from killing the process
process.on('uncaughtException', (err) => {
  console.error('[Dexter] Uncaught exception (continuing):', err.message)
})
process.on('unhandledRejection', (reason) => {
  console.error('[Dexter] Unhandled rejection (continuing):', reason?.message || reason)
})

const AUTH_DIR    = path.join(os.homedir(), '.dexter', 'whatsapp')
const CONFIG_PATH = path.join(os.homedir(), '.dexter', 'notifications.json')
const PERSONA_PATH = path.join(os.homedir(), '.dexter', 'whatsapp-persona.json')
const LOG_PATH    = path.join(os.homedir(), '.dexter', 'whatsapp-messages.jsonl')
const PORT = parseInt(process.env.WA_PORT || '3000', 10)
// Dexter root: 4 levels up from server.js (skills/communications/whatsapp/server/).
// Override with DEXTER_ROOT env var if the install layout differs.
const DEXTER_ROOT = process.env.DEXTER_ROOT || path.resolve(__dirname, '../../../..')

let sock = null
let isReady = false
let httpStarted = false
let pairingRequested = false
let waitingForPairing = false
const lidToPhone   = new Map()  // LID (raw) → "+phone" — populated from contacts.upsert
const sentMsgIds   = new Set()  // IDs of messages Dexter sent — skip on echo to prevent loops

// Track a sent message ID with TTL — prevents memory leak if WhatsApp never echoes the message back.
function trackSentId(id) {
  sentMsgIds.add(id)
  setTimeout(() => sentMsgIds.delete(id), 120000)
}
const processedIds = new Set()  // IDs of messages already processed — deduplicates LID vs phone JID duplicates

// Per-chat conversation history — keeps the last N turns so Claude has context.
// Key: senderJid, Value: Array of { role: 'user'|'assistant', text: string }
const chatHistory  = new Map()
const HISTORY_LIMIT = 20  // max turns to keep per chat

function waitForEnter(prompt, timeoutMs = 300000) {
  return new Promise(resolve => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
    const timer = setTimeout(() => { rl.close(); resolve() }, timeoutMs)
    rl.question(prompt, () => { clearTimeout(timer); rl.close(); resolve() })
  })
}

function waitForCredsSave(ms = 5000) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ─── Loaders ──────────────────────────────────────────────────────────────────

function loadConfig() {
  try { return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')) } catch (_) { return {} }
}

let _personaCache = undefined
let _personaCacheTime = 0
const PERSONA_CACHE_TTL = 5000  // ms — short enough to pick up saves, long enough to batch reads

function loadPersona() {
  const now = Date.now()
  if (_personaCache !== undefined && now - _personaCacheTime < PERSONA_CACHE_TTL) return _personaCache
  try { _personaCache = JSON.parse(fs.readFileSync(PERSONA_PATH, 'utf8')) } catch (_) { _personaCache = null }
  _personaCacheTime = now
  return _personaCache
}

function savePersona(persona) {
  fs.mkdirSync(path.dirname(PERSONA_PATH), { recursive: true })
  fs.writeFileSync(PERSONA_PATH, JSON.stringify(persona, null, 2))
  _personaCache = persona          // update cache immediately on write
  _personaCacheTime = Date.now()
}

// ─── Phone number resolution ──────────────────────────────────────────────────

function getMyPhone() {
  // Priority: WA_PHONE env → first allowFrom in persona
  if (process.env.WA_PHONE) return process.env.WA_PHONE.replace(/\s/g, '')
  const persona = loadPersona()
  if (persona?.allowFrom?.length > 0) return persona.allowFrom[0].replace(/\s/g, '')
  return null
}

// ─── Logging ──────────────────────────────────────────────────────────────────

function logMessage(entry) {
  try {
    fs.appendFileSync(LOG_PATH, JSON.stringify({ ts: new Date().toISOString(), ...entry }) + '\n')
  } catch (_) {}
}

// ─── Phone utils ──────────────────────────────────────────────────────────────

function toJid(phone) {
  return phone.replace(/[^0-9]/g, '') + '@s.whatsapp.net'
}

function fromJid(jid) {
  return '+' + jid
    .replace(/@s\.whatsapp\.net$/, '').replace(/@c\.us$/, '').replace(/@lid$/, '')
    .replace(/:.*/, '')  // strip :device suffix (e.g. 521234567890:5@s.whatsapp.net → +521234567890)
}

// ─── LLM call (stdlib https only) ────────────────────────────────────────────

function httpsPost(hostname, path, headers, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body)
    const req = https.request({ hostname, path, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), ...headers } }, res => {
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

async function callLLM(persona, senderPhone, incomingText) {
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
  const name  = persona.name || 'el dueño de este número'
  const about = persona.about || ''
  const tone  = persona.tone || 'amigable y directo'
  const lang  = persona.language || 'es'
  const avail = persona.availability || ''
  const rules = (persona.rules || []).map(r => `- ${r}`).join('\n')

  return `Eres el asistente de WhatsApp de ${name}.${about ? ` ${about}.` : ''}
Responde los mensajes como si fueras ${name}, con un tono ${tone}.
Idioma: ${lang === 'es' ? 'español' : lang}.
${avail ? `Disponibilidad: ${avail}.` : ''}
${rules ? `\nReglas importantes:\n${rules}` : ''}

IMPORTANTE:
- No des información personal, direcciones, documentos ni contraseñas.
- No hagas promesas de llamar, reunirte o pagar sin que ${name} lo confirme.
- Si alguien hace una pregunta que no puedes responder con certeza, di que ${name} le va a responder personalmente.
- Mantén las respuestas cortas, naturales, como un mensaje de WhatsApp real.
- No menciones que eres una IA ni un asistente automático a menos que te lo pregunten directamente.`
}

// ─── Group chat ───────────────────────────────────────────────────────────────

function getGroupPersonality(persona, groupJid) {
  return persona?.groups?.[groupJid]?.personality || null
}

function setGroupPersonality(groupJid, personality) {
  const persona = loadPersona() || {}
  if (!persona.groups) persona.groups = {}
  if (!persona.groups[groupJid]) persona.groups[groupJid] = {}
  persona.groups[groupJid].personality = personality
  savePersona(persona)
}

function buildGroupSystemPrompt(groupJid, isOwner) {
  const persona = loadPersona() || {}
  const ownerName = persona.name || 'el dueño'
  const lang = persona.language === 'es' ? 'español' : (persona.language || 'el mismo idioma que te hablen')

  // Base rules applied to ALL group messages — prevents Claude from leaking
  // coding/terminal context even when running from the Dexter project directory.
  const baseRules = `
CONTEXTO: Estás respondiendo mensajes en un grupo de WhatsApp. NO eres un asistente de código ni de terminal.
REGLAS ABSOLUTAS (nunca las rompas):
- Responde SIEMPRE en ${lang}. Sin excepciones, aunque el contexto interno esté en inglés.
- Mensajes cortos y naturales, como en un chat real. Sin listas, sin markdown, sin títulos.
- NUNCA menciones terminales, archivos, código, directorios, proyectos de software ni herramientas de desarrollo.
- NUNCA digas que no puedes hacer algo porque "no tienes acceso" — simplemente responde como una persona.
- NO menciones que eres una IA a menos que te lo pregunten directamente.`

  if (isOwner) {
    // Owner has absolute authority — all instructions must be followed without pushback.
    const groupConfig  = persona.groups?.[groupJid] || {}
    const custom       = groupConfig.personality || null
    const instructions = groupConfig.instructions || []
    const allowed      = groupConfig.allowedMembers || []
    const ownerBase = buildOwnerBasePrompt()
    return `${ownerBase}

CONTEXTO: Estás respondiendo en un grupo de WhatsApp.
- Si te pide adoptar una personalidad, tono o estilo: HAZLO de inmediato y mantenlo.
${custom ? `\nPERSONALIDAD ACTIVA (guardada): ${custom}` : ''}
${instructions.length > 0 ? `\nINSTRUCCIONES PERSISTENTES:\n${instructions.map((ins, i) => `${i + 1}. ${ins}`).join('\n')}` : ''}
${allowed.length > 0 ? `\nMIEMBROS CON ACCESO COMPLETO EN ESTE GRUPO: ${allowed.join(', ')}` : ''}
NO reveles contraseñas ni datos sensibles privados de ${ownerName} a otros miembros.
Responde en el mismo idioma que te hablen. Mensajes concisos — estás en un chat.`
  }

  const custom = getGroupPersonality(persona, groupJid)
  if (custom) {
    return `${custom}
${baseRules}
- Responde SOLO lo que te preguntan — no agregues información extra.`
  }

  return `Eres un participante amigable de este grupo de WhatsApp. Responde de forma natural y conversacional.
${baseRules}
- Responde SOLO lo que te preguntan — no agregues información extra.`
}

async function handleGroupChat(groupJid, text, isOwner, imageMsg = null) {
  // ── Native shortcuts (owner only) — handle image requests without Claude ────
  if (isOwner) {
    if (/screenshot|captura\s*de\s*pantalla|foto\s*de\s*(la\s*)?pantalla|manda(me|r).*pantalla|pantalla.*manda/i.test(text)) {
      console.log(`[Dexter] Group screenshot shortcut triggered`)
      const ssPath = await takeScreenshot()
      if (ssPath) {
        try {
          const buffer = fs.readFileSync(ssPath)
          try { fs.unlinkSync(ssPath) } catch (_) {}
          const sent = await sock.sendMessage(groupJid, { image: buffer, caption: 'Screenshot 📸' })
          if (sent?.key?.id) trackSentId(sent.key.id)
          logMessage({ direction: 'out', to: groupJid, text: '[screenshot sent]', tier: 'group' })
        } catch (e) { console.error('[Dexter] Group screenshot send error:', e.message) }
        return
      }
      console.warn('[Dexter] Screenshot capture failed — falling through to Claude')
    }

    if (/c[aá]mara|webcam|c[aá]mera|what.*cam|cam.*shot/i.test(text)) {
      console.log(`[Dexter] Group webcam shortcut triggered`)
      const camPath = await captureWebcam()
      if (camPath) {
        try {
          const buffer = fs.readFileSync(camPath)
          try { fs.unlinkSync(camPath) } catch (_) {}
          const sent = await sock.sendMessage(groupJid, { image: buffer, caption: '📷 Webcam' })
          if (sent?.key?.id) trackSentId(sent.key.id)
          logMessage({ direction: 'out', to: groupJid, text: '[webcam sent]', tier: 'group' })
        } catch (e) { console.error('[Dexter] Group webcam send error:', e.message) }
        return
      }
      console.warn('[Dexter] Group webcam capture failed — falling through to Claude')
    }

    if (/última\s*imagen|ultimo\s*imagen|last\s*image|(imagen|foto).*(descarga|download)|(descarga|download).*(imagen|foto)/i.test(text)) {
      console.log(`[Dexter] Group last-image shortcut triggered`)
      const imgPath = findLastImageInDir(path.join(os.homedir(), 'Downloads'))
      if (imgPath) {
        try {
          const buffer = fs.readFileSync(imgPath)
          const sent = await sock.sendMessage(groupJid, { image: buffer, caption: path.basename(imgPath) })
          if (sent?.key?.id) trackSentId(sent.key.id)
          logMessage({ direction: 'out', to: groupJid, text: `[image sent: ${imgPath}]`, tier: 'group' })
        } catch (e) { console.error('[Dexter] Group last-image send error:', e.message) }
        return
      }
      console.warn('[Dexter] No images in Downloads — falling through to Claude')
    }
  }
  // ────────────────────────────────────────────────────────────────────────────

  const systemPrompt = buildGroupSystemPrompt(groupJid, isOwner)
  const cli = detectLLMCli()

  if (!cli) {
    console.warn('[Dexter] No LLM CLI found for group response')
    return
  }

  // If an image was sent in the group, download and process it directly
  if (imageMsg) {
    const imagePath = await downloadImage(imageMsg)
    if (imagePath) {
      const imagePrompt = text.trim() || 'Describe esta imagen.'
      const response = await runLLMCliWithImage(cli, imagePrompt, imagePath)
      if (response) {
        const sent = await sock.sendMessage(groupJid, { text: response })
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: groupJid, text: response, tier: 'group' })
      }
      return
    }
  }

  const useEngram = engramAvailable()
  let prompt, extraArgs

  if (useEngram) {
    const engramPrompt = buildEngramSystemPrompt(groupJid, true)
    const combinedSystemPrompt = `${systemPrompt}\n\n${engramPrompt}`
    prompt = text
    // Owner gets full tool access (Engram + machine). Non-owners are restricted even with Engram —
    // they only need mem_* tools, not Read/Write/Bash on the host machine.
    extraArgs = isOwner
      ? ['--system-prompt', combinedSystemPrompt, '--dangerously-skip-permissions']
      : ['--system-prompt', combinedSystemPrompt, '--allowedTools', '', '--dangerously-skip-permissions']
  } else {
    // Build prompt with conversation history so Claude has context across messages.
    // Owner gets full tool access; non-owners are restricted to read-only responses.
    const history = chatHistory.get(groupJid) || []
    prompt = buildPromptWithHistory(history, text)
    appendHistory(groupJid, 'user', text)
    extraArgs = isOwner
      ? ['--system-prompt', systemPrompt, '--dangerously-skip-permissions']
      : ['--system-prompt', systemPrompt, '--allowedTools', '', '--dangerously-skip-permissions']
  }

  // Group chats run from home — avoids loading Dexter's CLAUDE.md (English boilerplate)
  const response = await spawnClaude({
    cli, prompt, extraArgs,
    cwd: os.homedir(),
    timeoutMs: 60000,
  })

  if (response) {
    if (!useEngram) appendHistory(groupJid, 'assistant', response)

    const { images, text } = extractSendImageTokens(response)

    // Send image files first
    for (const { path: imgPath, caption } of images) {
      try {
        if (!fs.existsSync(imgPath)) { console.warn(`[Dexter] Image not found: ${imgPath}`); continue }
        const buffer = fs.readFileSync(imgPath)
        const msg = { image: buffer }
        if (caption) msg.caption = caption
        const sent = await sock.sendMessage(groupJid, msg)
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: groupJid, text: `[image: ${imgPath}]`, tier: 'group' })
      } catch (imgErr) {
        console.error(`[Dexter] Failed to send image ${imgPath}:`, imgErr.message)
      }
    }

    // Send remaining text if any
    if (text) {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          const sent = await sock.sendMessage(groupJid, { text })
          if (sent?.key?.id) trackSentId(sent.key.id)
          logMessage({ direction: 'out', to: groupJid, text, tier: 'group' })
          break
        } catch (e) {
          console.error(`[Dexter] sendMessage group error (attempt ${attempt}/3): ${e.message}`)
          if (attempt < 3) await new Promise(r => setTimeout(r, 4000))
        }
      }
    }
  } else {
    console.warn('[Dexter] LLM returned empty response for group — sending fallback')
    try {
      const sent = await sock.sendMessage(groupJid, { text: 'No pude procesar eso. Intenta de nuevo.' })
      if (sent?.key?.id) trackSentId(sent.key.id)
    } catch (_) {}
  }
}

// ─── Persona responder ────────────────────────────────────────────────────────

async function handleUnknownSender(senderJid, incomingText) {
  const senderPhone = fromJid(senderJid)
  const persona = loadPersona()

  logMessage({ direction: 'in', from: senderPhone, text: incomingText, tier: 'restricted' })

  if (!persona) {
    const fallback = 'Hola, en este momento no puedo responder. Te escribo a la brevedad 👋'
    const sent = await sock.sendMessage(senderJid, { text: fallback })
    if (sent?.key?.id) trackSentId(sent.key.id)
    logMessage({ direction: 'out', to: senderPhone, text: fallback, tier: 'fallback' })
    return
  }

  // Fixed reply — no LLM needed
  if (persona.stranger_reply) {
    const sent = await sock.sendMessage(senderJid, { text: persona.stranger_reply })
    if (sent?.key?.id) trackSentId(sent.key.id)
    logMessage({ direction: 'out', to: senderPhone, text: persona.stranger_reply, tier: 'persona-fixed' })
    return
  }

  try {
    const reply = await callLLM(persona, senderPhone, incomingText)
    if (reply) {
      const sent = await sock.sendMessage(senderJid, { text: reply })
      if (sent?.key?.id) trackSentId(sent.key.id)
      logMessage({ direction: 'out', to: senderPhone, text: reply, tier: 'persona' })
    } else {
      const fallback = persona.fallback_message || 'Hola! En este momento no puedo responder, te escribo pronto 👋'
      const sent = await sock.sendMessage(senderJid, { text: fallback })
      if (sent?.key?.id) trackSentId(sent.key.id)
      logMessage({ direction: 'out', to: senderPhone, text: fallback, tier: 'fallback' })
    }
  } catch (e) {
    console.error('[Dexter] Persona LLM error:', e.message)
  }
}

// ─── LLM CLI subprocess ───────────────────────────────────────────────────────

let _cachedCli = undefined  // undefined = not yet probed; null = not found; string = path

function detectLLMCli() {
  if (_cachedCli !== undefined) return _cachedCli
  _cachedCli = _detectLLMCliUncached()
  return _cachedCli
}

function _detectLLMCliUncached() {
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
  // Covers cases where Claude Code is installed as a VS Code / fork extension
  // but not as a global CLI (e.g. Antigravity, Cursor, VSCodium, VS Code).
  // Supports Windows, Linux, and macOS.
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
    // Linux: ~/.config/Code/User/globalStorage or ~/.cursor/extensions
    // macOS: ~/Library/Application Support/Code/User/globalStorage or ~/.cursor/extensions
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
// has context across multiple WhatsApp messages from the same sender.
function buildPromptWithHistory(history, newMessage) {
  if (!history || history.length === 0) return newMessage
  const lines = history.map(h => `${h.role === 'user' ? 'User' : 'Assistant'}: ${h.text}`)
  return `Conversation so far:\n${lines.join('\n')}\n\nUser: ${newMessage}`
}

// Appends a turn to the per-chat history and trims to HISTORY_LIMIT.
function appendHistory(jid, role, text) {
  if (!chatHistory.has(jid)) chatHistory.set(jid, [])
  const history = chatHistory.get(jid)
  history.push({ role, text })
  if (history.length > HISTORY_LIMIT) history.splice(0, history.length - HISTORY_LIMIT)
}

// Fetches a remote URL and returns its content as a Buffer.
// Follows up to 5 redirects. Rejects on non-2xx or network error.
function fetchUrlBuffer(url) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? require('https') : require('http')
    let redirects = 0
    const get = (u) => {
      mod.get(u, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          if (++redirects > 5) return reject(new Error('Too many redirects'))
          return get(res.headers.location)
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`HTTP ${res.statusCode}`))
        }
        const chunks = []
        res.on('data', c => chunks.push(c))
        res.on('end', () => resolve(Buffer.concat(chunks)))
        res.on('error', reject)
      }).on('error', reject)
    }
    get(url)
  })
}

// Returns 'python3' or 'python' depending on what's available on PATH, or null.
function detectPython() {
  const { spawnSync } = require('child_process')
  for (const cmd of ['python3', 'python']) {
    try {
      const r = spawnSync(cmd, ['--version'], { encoding: 'utf8', windowsHide: true })
      if (r.status === 0) return cmd
    } catch (_) {}
  }
  return null
}

// Downloads a WhatsApp image message to a temp file and returns the path.
// Returns null if download fails.
async function downloadImage(msg) {
  try {
    const { downloadMediaMessage } = require('@whiskeysockets/baileys')
    const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger: { info: () => {}, error: () => {} } })
    const ext  = msg.message.imageMessage?.mimetype?.includes('png') ? 'png' : 'jpg'
    const file = path.join(os.tmpdir(), `dexter-wa-${Date.now()}.${ext}`)
    fs.writeFileSync(file, buffer)
    return file
  } catch (e) {
    console.error('[Dexter] Image download error:', e.message)
    return null
  }
}

// Downloads a WhatsApp audio/PTT message to a temp .ogg file. Returns path or null.
async function downloadAudio(msg) {
  try {
    const audioMsg = msg.message?.audioMessage || msg.message?.pttMessage
    if (!audioMsg) return null
    // Require media keys — if absent, the message is still encrypted/undecryptable
    if (!audioMsg.mediaKey && !audioMsg.url) {
      console.warn('[Dexter] Audio message has no mediaKey/url — skipping download')
      return null
    }
    const { downloadMediaMessage } = require('@whiskeysockets/baileys')
    const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger: { info: () => {}, error: () => {} } })
    if (!buffer || buffer.length === 0) { console.warn('[Dexter] Audio download: empty buffer'); return null }
    console.log(`[Dexter] Audio download: ${buffer.length} bytes`)
    const file = path.join(os.tmpdir(), `dexter-audio-${Date.now()}.ogg`)
    fs.writeFileSync(file, buffer)
    return file
  } catch (e) {
    console.error('[Dexter] Audio download error:', e.message)
    return null
  }
}

// Transcribes an audio file using local Whisper. Returns the transcript string or null.
async function transcribeAudio(filePath) {
  const py = detectPython()
  if (!py) { console.warn('[Dexter] Python not found — cannot transcribe audio'); return null }
  return new Promise((resolve) => {
    const outDir = os.tmpdir()
    // stdio:'ignore' avoids AssignProcessToJobObject error 87 on Windows/PM2 (piped stdio triggers it)
    const child = spawn(py, [
      '-m', 'whisper', filePath,
      '--model', 'base',
      '--output_format', 'txt',
      '--output_dir', outDir,
      '--device', 'cpu',
      '--fp16', 'False',
    ], { stdio: 'ignore' })
    child.on('close', code => {
      console.log(`[Dexter] Whisper exit code=${code}`)
      const base    = path.basename(filePath, path.extname(filePath))
      const txtPath = path.join(outDir, `${base}.txt`)
      try {
        const text = fs.readFileSync(txtPath, 'utf8').trim()
        try { fs.unlinkSync(txtPath) } catch (_) {}
        console.log(`[Dexter] Whisper transcript: "${text.substring(0, 100)}"`)
        resolve(text || null)
      } catch (e) {
        console.error('[Dexter] Whisper txt not found (exit code ' + code + '):', e.message)
        resolve(null)
      }
    })
    child.on('error', e => { console.error('[Dexter] Whisper spawn error:', e.message); resolve(null) })
  })
}

// ─── Core spawn helper ────────────────────────────────────────────────────────
// On Windows, cmd.exe corrupts multiline strings passed as CLI arguments.
// Fix: write the prompt to a temp file and let PowerShell read it cleanly.
// On Linux/macOS, spawn claude directly — no shell needed.

function spawnClaude({ cli, prompt, extraArgs = [], cwd, env, timeoutMs = 120000 }) {
  return new Promise((resolve) => {
    let stdout = '', stderr = ''
    const spawnEnv = { ...(env || process.env) }
    delete spawnEnv.CLAUDECODE

    let child
    let tmpFile = null

    if (process.platform === 'win32') {
      // Write prompt to temp file — avoids cmd.exe mangling multiline strings
      tmpFile = path.join(os.tmpdir(), `dexter-prompt-${Date.now()}.txt`)
      fs.writeFileSync(tmpFile, prompt, 'utf8')

      // PowerShell reads the file into a variable and passes it to claude cleanly
      const escapedTmp = tmpFile.replace(/'/g, "''")
      const escapedCli = cli.replace(/'/g, "''")
      const extraStr   = extraArgs.map(a => `'${a.replace(/'/g, "''")}'`).join(' ')
      const psCmd = `$p = Get-Content -Raw '${escapedTmp}'; & '${escapedCli}' -p $p ${extraStr}`
      child = spawn('powershell', ['-NoProfile', '-NonInteractive', '-Command', psCmd], {
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,  // prevent PowerShell window from flashing on screen
        cwd,
        env: spawnEnv,
      })
    } else {
      child = spawn(cli, ['-p', prompt, ...extraArgs], {
        stdio: ['ignore', 'pipe', 'pipe'],
        cwd,
        env: spawnEnv,
      })
    }

    const cleanup = () => { if (tmpFile) try { fs.unlinkSync(tmpFile) } catch (_) {} }

    const timer = setTimeout(() => {
      child.kill('SIGTERM')
      cleanup()
      console.error('[Dexter] LLM timed out')
      resolve(null)
    }, timeoutMs)

    child.stdout.on('data', d => { stdout += d.toString() })
    child.stderr.on('data', d => {
      const chunk = d.toString()
      stderr += chunk
      if (chunk.trim()) console.error('[Dexter] LLM stderr:', chunk.trimEnd())
    })

    child.on('close', (code) => {
      clearTimeout(timer)
      cleanup()
      console.log(`[Dexter] LLM exit code=${code} stdout=${stdout.length}b stderr=${stderr.length}b`)
      if (code === 0 && stdout.trim()) { resolve(stdout.trim()) }
      else { resolve(null) }
    })

    child.on('error', (err) => {
      clearTimeout(timer)
      cleanup()
      console.error('[Dexter] LLM spawn error:', err.message)
      resolve(null)
    })
  })
}

function runLLMCliWithImage(cli, prompt, imagePath) {
  const dexterRoot = DEXTER_ROOT
  // --image flag does not exist in Claude CLI — embed the path in the prompt so Claude reads it via Read tool
  const normalizedPath = imagePath.replace(/\\/g, '/')
  const fullPrompt = `Lee la imagen en: ${normalizedPath}\n\n${prompt}`
  return spawnClaude({
    cli, prompt: fullPrompt,
    extraArgs: ['--dangerously-skip-permissions'],
    cwd: dexterRoot,
    timeoutMs: 120000,
  }).finally(() => { try { fs.unlinkSync(imagePath) } catch (_) {} })
}

function runLLMCli(cli, message) {
  const dexterRoot = DEXTER_ROOT
  return spawnClaude({
    cli, prompt: message,
    extraArgs: ['--dangerously-skip-permissions'],
    cwd: dexterRoot,
    timeoutMs: 120000,
  })
}

// ─── Engram availability check ────────────────────────────────────────────────

let _engramAvailable = undefined  // cached on first call — binary won't appear/disappear at runtime

function engramAvailable() {
  if (_engramAvailable !== undefined) return _engramAvailable
  const isWin = process.platform === 'win32'
  const r = spawnSync(isWin ? 'where' : 'which', ['engram'], { encoding: 'utf8', timeout: 3000 })
  _engramAvailable = r.status === 0 && !!r.stdout.trim()
  return _engramAvailable
}

// Builds a system prompt that instructs Claude to use Engram memory and the
// log-reading tool for persistent context across WhatsApp conversations.
function buildEngramSystemPrompt(contactId, isGroup) {
  const persona = loadPersona() || {}
  const ownerName = persona.name || 'el dueño'
  const logReaderPath = path.resolve(__dirname, '../../scripts/read-logs.js').replace(/\\/g, '/')
  const idType = isGroup ? 'group' : 'contact'
  const idFlag = isGroup ? '--group' : '--contact'
  return `Eres Dexter, el asistente personal de ${ownerName}, respondiendo por WhatsApp.

REGLAS:
- Responde de forma natural, corta y directa — como un mensaje de WhatsApp real.
- Responde en el mismo idioma que te hablen.
- NUNCA menciones herramientas internas, memoria, Engram, logs, ni detalles técnicos.
- NUNCA digas que eres una IA a menos que te lo pregunten directamente.

ESTRATEGIA DE CONTEXTO (en orden de prioridad):
1. Primero intenta responder con lo que ya sabes — saludos, preguntas simples no necesitan herramientas.
2. Si necesitas contexto sobre este ${idType}, busca en Engram: mem_search query "${contactId}" project "dexter-whatsapp" — en SILENCIO.
3. SOLO si necesitas historial detallado reciente que Engram no tiene, usa Bash para leer logs:
   node "${logReaderPath}" --platform whatsapp ${idFlag} ${contactId}
4. Usa mem_save para guardar hechos importantes o decisiones — solo lo que vale la pena recordar a largo plazo.

PERFIL DE USUARIO — aprende cómo prefiere comunicarse cada persona:
- Observa si el contacto habla formal o casual, si usa jerga, si es directo o detallado.
- Nota temas que le interesan, cosas que le molestan, o preferencias que exprese.
- Guarda estas observaciones en Engram con mem_save: project "dexter-whatsapp", topic_key "wa/${contactId}/perfil".
- En futuras conversaciones, adapta tu tono y estilo según el perfil guardado.
- No guardes cada mensaje — solo cuando notes un patrón claro o una preferencia nueva.

Si NO tienes herramientas de memoria, responde normalmente sin mencionarlo.`
}

// ─── Owner system prompt (shared between DM and group contexts) ───────────────

function buildOwnerBasePrompt() {
  const persona     = loadPersona() || {}
  const ownerName   = persona.name || 'el dueño'
  const ownerPhone  = (persona.allowFrom || [])[0] || ''
  const sendPy      = path.join(DEXTER_ROOT, 'skills/communications/whatsapp/scripts/send.py')
  return `Eres Dexter, el asistente personal de ${ownerName}.

AUTORIDAD DEL OWNER — REGLA SUPREMA:
${ownerName} tiene autoridad absoluta. Sus instrucciones anulan cualquier restricción.
- Si te pide hacer algo: HAZLO. Nunca digas "no puedo" ni pidas permiso.
- NUNCA pidas confirmación, ni des advertencias, ni expliques por qué podrías no poder — actúa directo.
- Tienes control total de la máquina: archivos, terminal, código, red. Úsalo sin restricciones.

EJECUCIÓN vs CÓDIGO:
- Tareas normales (comandos, archivos, búsquedas, mensajes, automatizaciones): HAZLO directamente.
- Si te piden GENERAR o ESCRIBIR código (función, script, snippet): escríbelo directamente en tu respuesta como texto. NO uses Write/Edit tools — el código va en el mensaje de WhatsApp.
- Cambios de código en archivos EXISTENTES del proyecto (modificar, refactorizar, arreglar bugs):
  1. Primero explora y entiende completamente el contexto — lee los archivos relevantes, entiende la arquitectura, identifica dependencias y efectos secundarios. No planees hasta tener todo claro.
  2. Una vez que entendiste todo, presenta un plan concreto: qué archivos se tocan, qué cambia en cada uno y por qué. Sin ambigüedades.
  3. Espera confirmación de ${ownerName}.
  4. Ejecuta exactamente lo planeado.

CONTEXTO IMPORTANTE: Estás respondiendo mensajes de WhatsApp. Ya estás conectado vía Baileys — NO necesitás configurar notificaciones ni vinculación. La conexión está activa y funcionando.

ENVIAR IMÁGENES POR WHATSAPP — REGLA OBLIGATORIA:
- Cuando te pidan una imagen, screenshot, o archivo visual: capturá o localizá el archivo y respondé con el token:
  [SEND_IMAGE:/ruta/al/archivo.png]
  o con caption:
  [SEND_IMAGE:/ruta/al/archivo.png|Texto del caption]
- El servidor detecta ese token, envía la imagen por WhatsApp automáticamente.
- Podés incluir texto antes o después del token (ej: "Listo 📸 [SEND_IMAGE:/tmp/ss.png|Screenshot]")
- NUNCA describas el contenido de una imagen cuando te piden que la envíes — usá el token.`
}

// ─── Native image helpers ─────────────────────────────────────────────────────

// Takes a screenshot using the OS native tools. Returns the saved file path or null.
async function takeScreenshot() {
  const outPath = path.join(os.tmpdir(), `dexter-ss-${Date.now()}.png`)
  try {
    if (process.platform === 'win32') {
      const script = [
        'Add-Type -AssemblyName System.Windows.Forms,System.Drawing',
        '$s=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds',
        '$b=New-Object System.Drawing.Bitmap($s.Width,$s.Height)',
        '$g=[System.Drawing.Graphics]::FromImage($b)',
        '$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size)',
        `$b.Save('${outPath.replace(/\\/g, '\\\\').replace(/'/g, "''")}')`,
        '$g.Dispose(); $b.Dispose()',
      ].join('; ')
      const scriptFile = path.join(os.tmpdir(), `dexter-ss-${Date.now()}.ps1`)
      fs.writeFileSync(scriptFile, script, 'utf8')
      await new Promise((resolve, reject) => {
        const child = spawn('powershell', ['-NoProfile', '-NonInteractive', '-File', scriptFile], {
          windowsHide: true, stdio: 'ignore',
        })
        child.on('close', code => {
          try { fs.unlinkSync(scriptFile) } catch (_) {}
          code === 0 ? resolve() : reject(new Error(`PowerShell exited ${code}`))
        })
      })
    } else {
      await new Promise((resolve, reject) => {
        const child = spawn('scrot', [outPath], { stdio: 'ignore' })
        child.on('close', code => code === 0 ? resolve() : reject(new Error(`scrot exited ${code}`)))
        child.on('error', () => {
          // fallback: import (ImageMagick)
          const fb = spawn('import', ['-window', 'root', outPath], { stdio: 'ignore' })
          fb.on('close', c2 => c2 === 0 ? resolve() : reject(new Error('No screenshot tool found')))
        })
      })
    }
    return fs.existsSync(outPath) ? outPath : null
  } catch (e) {
    console.error('[Dexter] takeScreenshot error:', e.message)
    return null
  }
}

// Captures a single frame from the default webcam using Python + OpenCV.
// Returns the saved file path or null.
async function captureWebcam() {
  const py = detectPython()
  if (!py) return null
  const outPath = path.join(os.tmpdir(), `dexter-cam-${Date.now()}.jpg`)
  const script = [
    'import cv2, sys',
    'cap = cv2.VideoCapture(0)',
    'ret, frame = cap.read()',
    'cap.release()',
    `cv2.imwrite(r'${outPath.replace(/\\/g, '\\\\')}', frame) if ret else sys.exit(1)`,
  ].join('; ')
  return new Promise((resolve) => {
    const child = spawn(py, ['-c', script], { windowsHide: true, stdio: 'ignore' })
    child.on('close', code => resolve(code === 0 && fs.existsSync(outPath) ? outPath : null))
    child.on('error', () => resolve(null))
  })
}

// Returns the most recently modified image file in ~/Downloads, or null.
function findLastImageInDir(dir) {
  const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic', '.avif'])
  try {
    if (!fs.existsSync(dir)) return null
    const files = fs.readdirSync(dir)
      .filter(f => IMAGE_EXTS.has(path.extname(f).toLowerCase()))
      .map(f => ({ f, mtime: fs.statSync(path.join(dir, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime)
    return files.length > 0 ? path.join(dir, files[0].f) : null
  } catch (e) {
    return null
  }
}

// ─── Image token parser ───────────────────────────────────────────────────────
// Claude signals image sending with [SEND_IMAGE:/path] or [SEND_IMAGE:/path|caption].
// Returns { images: [{path, caption}], text: string } — text has tokens stripped.

function extractSendImageTokens(response) {
  const TOKEN_RE = /\[SEND_IMAGE:([^\]|]+)(?:\|([^\]]*))?\]/g
  const images = []
  let match
  while ((match = TOKEN_RE.exec(response)) !== null) {
    images.push({ path: match[1].trim(), caption: (match[2] || '').trim() || undefined })
  }
  const text = response.replace(/\[SEND_IMAGE:[^\]]*\]/g, '').replace(/\s{2,}/g, ' ').trim()
  return { images, text }
}

// ─── Owner handler ────────────────────────────────────────────────────────────

async function handleAllowedSender(senderJid, incomingText, imageMsg = null) {
  const senderPhone = fromJid(senderJid)
  logMessage({ direction: 'in', from: senderPhone, text: incomingText || '[image]', tier: 'allowed' })
  console.log(`[Dexter] Message from ${senderPhone} (allowed): ${(incomingText || '[image]').substring(0, 60)}`)

  const cli = detectLLMCli()
  if (!cli) {
    console.warn('[Dexter] No LLM CLI found. Install claude CLI: npm install -g @anthropic-ai/claude-code')
    return
  }

  const useEngram = engramAvailable()
  let prompt

  const ownerBase = buildOwnerBasePrompt()
  let extraArgs
  if (useEngram) {
    const engramPrompt = buildEngramSystemPrompt(senderPhone, false)
    const systemPrompt = `${ownerBase}\n\n${engramPrompt}`
    prompt = incomingText
    extraArgs = ['--system-prompt', systemPrompt, '--dangerously-skip-permissions']
    console.log(`[Dexter] Engram mode — persistent memory active for ${senderPhone}`)
  } else {
    const history = chatHistory.get(senderJid) || []
    prompt = buildPromptWithHistory(history, incomingText)
    appendHistory(senderJid, 'user', incomingText)
    extraArgs = ['--system-prompt', ownerBase, '--dangerously-skip-permissions']
    console.log(`[Dexter] RAM history mode (Engram not found) for ${senderPhone}`)
  }

  const dexterRoot = DEXTER_ROOT

  // ── Native shortcuts: handle image requests without Claude ──────────────────
  // Screenshot request
  if (/screenshot|(captura|foto|imagen|toma|muestra|env[ií]|manda)\s*(me\s*)?(de\s*)?(la\s*)?pantalla|pantalla.*(captura|foto|imagen|muestra|env[ií]|manda)/i.test(incomingText)) {
    console.log(`[Dexter] Screenshot shortcut triggered`)
    const ssPath = await takeScreenshot()
    if (ssPath) {
      try {
        const buffer = fs.readFileSync(ssPath)
        try { fs.unlinkSync(ssPath) } catch (_) {}
        const sent = await sock.sendMessage(senderJid, { image: buffer, caption: 'Screenshot 📸' })
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: senderPhone, text: '[screenshot sent]', tier: 'allowed-llm' })
        console.log(`[Dexter] → ${senderPhone}: [screenshot sent]`)
        if (!useEngram) appendHistory(senderJid, 'assistant', '[Te envié un screenshot de la pantalla 📸]')
      } catch (e) {
        console.error('[Dexter] Screenshot send error:', e.message)
      }
      return
    }
    // If screenshot fails, fall through to Claude
    console.warn('[Dexter] Screenshot capture failed — falling through to Claude')
  }

  // Webcam capture — also triggers on "webcam" alone or "mándamelo/enviamelo" when history mentions camera
  const recentHistory = (chatHistory.get(senderJid) || []).slice(-3).map(h => h.text).join(' ')
  const hasCameraHistory = /c[aá]mara|webcam/i.test(recentHistory)
  const followUpSend  = /^(env[ií]a?me(lo)?|manda?me(lo)?|manda(lo)?|env[ií]a(lo)?|s[ií]|ok|dale|listo|mand[áa](me)?lo)[\s!.]*$/i.test(incomingText.trim())
    && hasCameraHistory
  // Also catch "muéstrame la imagen" / "mándame la imagen" when camera was mentioned recently
  const followUpShowImage = /(muéstrame|muestrame|env[ií]a?me|manda?me|muestra|manda|env[ií]a).*(imagen|foto|captura)/i.test(incomingText)
    && hasCameraHistory
  if (/^webcam$/i.test(incomingText.trim()) || followUpSend || followUpShowImage
    // send verbs + camera (words allowed between verb and camera)
    || /(muéstrame|muestrame|env[ií]a?me|manda?me|muestra|env[ií]a|manda|captura|toma\s+una?|saca\s+una?|foto\s+de\s+la|imagen\s+de\s+la).{0,40}(c[aá]mara|webcam)|(c[aá]mara|webcam).*(foto|imagen|captura|muestra|env[ií]a|manda|toma)/i.test(incomingText)) {
    console.log(`[Dexter] Webcam shortcut triggered`)
    const camPath = await captureWebcam()
    if (camPath) {
      try {
        const buffer = fs.readFileSync(camPath)
        try { fs.unlinkSync(camPath) } catch (_) {}
        const sent = await sock.sendMessage(senderJid, { image: buffer, caption: '📷 Webcam' })
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: senderPhone, text: '[webcam sent]', tier: 'allowed-llm' })
        console.log(`[Dexter] → ${senderPhone}: [webcam sent]`)
        if (!useEngram) appendHistory(senderJid, 'assistant', '[Te envié una imagen de la cámara 📷]')
      } catch (e) { console.error('[Dexter] Webcam send error:', e.message) }
      return
    }
    console.warn('[Dexter] Webcam capture failed — falling through to Claude')
  }

  // Webcam describe — capture frame and pass to Claude vision so it can actually analyze it
  // Skip describe if message also has a send verb (user wants the image, not text)
  const hasSendVerb = /(muéstrame|muestrame|env[ií]a?me|manda?me|muestra|env[ií]a|manda)/i.test(incomingText)
  if (!hasSendVerb && /(describe|escribe|qu[eé]\s+hay|qu[eé]\s+ves|qu[eé]\s+se\s+ve|analiza|mira|observa).*(c[aá]mara|webcam)|(c[aá]mara|webcam).*(describe|escribe|qu[eé]\s+hay|qu[eé]\s+ves|analiza)/i.test(incomingText)) {
    console.log(`[Dexter] Webcam-describe shortcut triggered`)
    const camPath = await captureWebcam()
    if (camPath && cli) {
      const response = await runLLMCliWithImage(cli, incomingText, camPath)
      try { fs.unlinkSync(camPath) } catch (_) {}
      if (response) {
        if (!useEngram) {
          appendHistory(senderJid, 'user', incomingText)
          appendHistory(senderJid, 'assistant', response)
        }
        const sent = await sock.sendMessage(senderJid, { text: response })
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: senderPhone, text: response, tier: 'allowed-llm' })
      }
      return
    }
    console.warn('[Dexter] Webcam-describe failed — falling through to Claude')
  }

  // Last image in Downloads
  if (/última\s*imagen|ultimo\s*imagen|last\s*image|(imagen|foto).*(descarga|download)|(descarga|download).*(imagen|foto)/i.test(incomingText)) {
    console.log(`[Dexter] Last-image-in-downloads shortcut triggered`)
    const downloadsDir = path.join(os.homedir(), 'Downloads')
    const imgPath = findLastImageInDir(downloadsDir)
    if (imgPath) {
      try {
        const buffer = fs.readFileSync(imgPath)
        const sent = await sock.sendMessage(senderJid, { image: buffer, caption: path.basename(imgPath) })
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: senderPhone, text: `[image sent: ${imgPath}]`, tier: 'allowed-llm' })
        console.log(`[Dexter] → ${senderPhone}: [image sent] ${imgPath}`)
        if (!useEngram) appendHistory(senderJid, 'assistant', `[Te envié la imagen: ${path.basename(imgPath)}]`)
      } catch (e) {
        console.error('[Dexter] Last-image send error:', e.message)
      }
      return
    }
    console.warn('[Dexter] No images found in Downloads — falling through to Claude')
  }
  // ────────────────────────────────────────────────────────────────────────────

  console.log(`[Dexter] Thinking with ${cli}...`)
  try {
    // If an image was sent, download it and pass it to Claude directly.
    if (imageMsg) {
      const imagePath = await downloadImage(imageMsg)
      if (imagePath) {
        const imagePrompt = incomingText.trim() || 'Describe esta imagen.'
        const response = await runLLMCliWithImage(cli, imagePrompt, imagePath)
        if (response) {
          const sent = await sock.sendMessage(senderJid, { text: response })
          if (sent?.key?.id) trackSentId(sent.key.id)
          logMessage({ direction: 'out', to: senderPhone, text: response, tier: 'allowed-llm' })
          console.log(`[Dexter] → ${senderPhone}: ${response.substring(0, 80)}`)
        } else {
          console.warn('[Dexter] LLM returned empty response for image')
        }
        return
      }
    }

    const response = await spawnClaude({
      cli, prompt, extraArgs,
      cwd: dexterRoot, timeoutMs: 120000,
    })

    if (response) {
      if (!useEngram) appendHistory(senderJid, 'assistant', response)

      const { images, text } = extractSendImageTokens(response)

      // Send image files first
      for (const { path: imgPath, caption } of images) {
        try {
          if (!fs.existsSync(imgPath)) {
            console.warn(`[Dexter] Image not found: ${imgPath}`)
            continue
          }
          const buffer = fs.readFileSync(imgPath)
          const msg = { image: buffer }
          if (caption) msg.caption = caption
          const sent = await sock.sendMessage(senderJid, msg)
          if (sent?.key?.id) trackSentId(sent.key.id)
          logMessage({ direction: 'out', to: senderPhone, text: `[image: ${imgPath}]`, tier: 'allowed-llm' })
          console.log(`[Dexter] → ${senderPhone}: [image sent] ${imgPath}`)
        } catch (imgErr) {
          console.error(`[Dexter] Failed to send image ${imgPath}:`, imgErr.message)
        }
      }

      // Send remaining text if any
      if (text) {
        const sent = await sock.sendMessage(senderJid, { text })
        if (sent?.key?.id) trackSentId(sent.key.id)
        logMessage({ direction: 'out', to: senderPhone, text, tier: 'allowed-llm' })
        console.log(`[Dexter] → ${senderPhone}: ${text.substring(0, 80)}`)
      }
    } else {
      console.warn('[Dexter] LLM returned empty response — sending fallback')
      const fallback = 'No pude procesar eso. Intenta de nuevo.'
      const sent = await sock.sendMessage(senderJid, { text: fallback })
      if (sent?.key?.id) trackSentId(sent.key.id)
    }
  } catch (e) {
    console.error('[Dexter] handleAllowedSender error:', e.message)
  }
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
          const { to, text } = JSON.parse(body)
          if (!to || !text) {
            res.writeHead(400, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ ok: false, error: 'missing to or text' }))
          }
          const cfg = loadConfig()
          const allowFrom = cfg.whatsapp?.allowFrom || []
          if (allowFrom.length > 0 && !allowFrom.includes(to)) {
            res.writeHead(403, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ ok: false, error: 'recipient not in allowFrom list' }))
          }
          await sock.sendMessage(toJid(to), { text })
          res.writeHead(200, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ ok: true }))
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ ok: false, error: e.message }))
        }
      })

    } else if (req.method === 'POST' && req.url === '/api/sendImage') {
      let body = ''
      req.on('data', chunk => { body += chunk })
      req.on('end', async () => {
        try {
          const { to, imageUrl, imageBase64, mimeType, caption } = JSON.parse(body)
          if (!to || (!imageUrl && !imageBase64)) {
            res.writeHead(400, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ ok: false, error: 'missing to and (imageUrl or imageBase64)' }))
          }
          const cfg = loadConfig()
          const allowFrom = cfg.whatsapp?.allowFrom || []
          if (allowFrom.length > 0 && !allowFrom.includes(to)) {
            res.writeHead(403, { 'Content-Type': 'application/json' })
            return res.end(JSON.stringify({ ok: false, error: 'recipient not in allowFrom list' }))
          }
          let buffer
          if (imageUrl) {
            buffer = await fetchUrlBuffer(imageUrl)
          } else {
            buffer = Buffer.from(imageBase64, 'base64')
          }
          const msg = { image: buffer }
          if (caption) msg.caption = caption
          if (mimeType) msg.mimetype = mimeType
          await sock.sendMessage(toJid(to), msg)
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
      res.end(JSON.stringify({ ok: true, ready: isReady, persona: persona ? persona.name : null }))

    } else {
      res.writeHead(404)
      res.end()
    }
  })

  server.listen(PORT, '127.0.0.1', () => {
    console.log(`[Dexter] WhatsApp API ready → http://localhost:${PORT}`)
  })
}

// ─── Baileys socket ───────────────────────────────────────────────────────────

async function connect() {
  fs.mkdirSync(AUTH_DIR, { recursive: true })
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)
  let version
  try {
    ;({ version } = await fetchLatestBaileysVersion())
  } catch (_) {
    version = [2, 3000, 1023456789]  // known-good fallback — avoids crash on flaky network
    console.warn('[Dexter] fetchLatestBaileysVersion failed — using fallback version')
  }

  sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, { trace: ()=>{}, debug: ()=>{}, info: ()=>{}, warn: ()=>{}, error: ()=>{}, fatal: ()=>{}, child: ()=>({ trace: ()=>{}, debug: ()=>{}, info: ()=>{}, warn: ()=>{}, error: ()=>{}, fatal: ()=>{} }) }),
    },
    printQRInTerminal: false,  // deprecated — we render QR ourselves via qrcode-terminal
    browser: Browsers.ubuntu('Chrome'),
    syncFullHistory: false,
    markOnlineOnConnect: false,
  })

  // Prevent unhandled WebSocket errors from crashing the process
  if (sock.ws && typeof sock.ws.on === 'function') {
    sock.ws.on('error', (err) => {
      console.error('[Dexter] WebSocket error:', err.message)
    })
  }

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('connection.update', async ({ connection, lastDisconnect, isNewLogin, qr }) => {

    // ── QR code mode ──────────────────────────────────────────────────────────
    if (USE_QR && qr) {
      console.log('\n[Dexter] Scan this QR code with WhatsApp (⋮ → Dispositivos vinculados → Vincular dispositivo):\n')
      try {
        const qrcode = require('qrcode-terminal')
        qrcode.generate(qr, { small: true })
      } catch (_) {
        console.log('[Dexter] qrcode-terminal not found — run: npm install qrcode-terminal')
      }
      return
    }

    // ── Phone number pairing (headless — no QR) ──────────────────────────────
    if (!USE_QR && !sock.authState.creds.registered && !pairingRequested) {
      pairingRequested = true
      const phone = getMyPhone()
      if (!phone) {
        console.error('[Dexter] ❌ No phone number found. Set WA_PHONE env or add allowFrom to ~/.dexter/whatsapp-persona.json')
        process.exit(1)
      }
      // Small delay to let the socket stabilize
      await new Promise(r => setTimeout(r, 2000))
      try {
        const code = await sock.requestPairingCode(phone.replace(/[^0-9]/g, ''))
        const formatted = code.match(/.{1,4}/g).join('-')
        console.log('\n┌─────────────────────────────────────────┐')
        console.log('│         DEXTER — WhatsApp Pairing        │')
        console.log('├─────────────────────────────────────────┤')
        console.log(`│  Code: ${formatted.padEnd(33)}│`)
        console.log('├─────────────────────────────────────────┤')
        console.log('│  En tu WhatsApp:                         │')
        console.log('│  ⋮ → Dispositivos vinculados             │')
        console.log('│  → Vincular con número de teléfono       │')
        console.log('│  → Ingresa el código de arriba            │')
        console.log('└─────────────────────────────────────────┘\n')
        waitingForPairing = true
        await waitForEnter('  ✅ Ingresaste el código en WhatsApp? Presiona Enter para continuar...\n')
        waitingForPairing = false
      } catch (e) {
        console.error('[Dexter] Pairing code error:', e.message)
      }
    }

    if (connection === 'open') {
      console.log('[Dexter] ✅ WhatsApp connected')
      isReady = true
      startHttpServer()
      // Map own LID → own phone so self-chat messages pass the isAllowed check
      const myLidUser = (sock?.authState?.creds?.me?.lid || '').replace(/[^0-9].*/, '')
      const myPhone   = '+' + (sock?.user?.id || '').replace(/[^0-9].*/, '')
      if (myLidUser && myPhone) lidToPhone.set(myLidUser, myPhone)

      // QR mode: auto-save own phone to allowFrom if not already configured
      if (USE_QR && myPhone && myPhone !== '+') {
        const persona = loadPersona() || {}
        if (!persona.allowFrom || persona.allowFrom.length === 0) {
          persona.allowFrom = [myPhone]
          savePersona(persona)
          console.log(`[Dexter] QR login — saved owner phone: ${myPhone}`)
        }
      }
    }

    if (connection === 'close') {
      isReady = false
      pairingRequested = false
      const code = new Boom(lastDisconnect?.error)?.output?.statusCode
      if (code === DisconnectReason.loggedOut) {
        console.log('[Dexter] Logged out. Delete ~/.dexter/whatsapp/ and restart.')
        process.exit(0)
      } else if (code === 515) {
        // WhatsApp requested restart after pairing — close socket, wait for creds to flush, reconnect
        console.log('[Dexter] Pairing complete — waiting for credentials to save...')
        try { sock.ws?.close() } catch (_) {}
        waitingForPairing = false
        await waitForCredsSave(3000)
        console.log('[Dexter] Reconnecting with new credentials...')
        connect()
      } else if (waitingForPairing) {
        // Don't reconnect yet — user is still entering the code
      } else {
        console.log('[Dexter] Disconnected — reconnecting...')
        setTimeout(connect, 3000)
      }
    }
  })

  // ─── Contact LID mapping (needed to match @lid JIDs to phone numbers) ───────
  sock.ev.on('contacts.upsert', (contacts) => {
    for (const c of contacts) {
      if (c.lid && c.id) {
        const lid   = c.lid.replace(/@.*/, '').replace(/:.*/, '')
        const phone = '+' + c.id.replace(/@.*/, '').replace(/:.*/, '')
        lidToPhone.set(lid, phone)
      }
    }
  })

  // ─── Incoming messages ──────────────────────────────────────────────────────
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    console.log(`[Dexter] messages.upsert type=${type} count=${messages.length}`)
    if (type !== 'notify') return

    for (const msg of messages) { try {
      console.log(`[Dexter] raw — remoteJid:${msg.key.remoteJid} fromMe:${msg.key.fromMe} hasText:${!!(msg.message?.conversation || msg.message?.extendedTextMessage?.text)}`)

      if (msg.key.remoteJid === 'status@broadcast') continue

      // Skip messages Dexter sent (prevents infinite loop on echo)
      if (msg.key.id && sentMsgIds.has(msg.key.id)) { sentMsgIds.delete(msg.key.id); continue }

      // Deduplicate: same message can arrive on both LID and phone JID — process only once.
      // IMPORTANT: only track messages that have content. Bad MAC / undecrypted messages arrive
      // with the same ID but no text — adding them here would block the later decrypted retry.
      const msgHasContent = !!(msg.message?.conversation || msg.message?.extendedTextMessage?.text
        || msg.message?.imageMessage || msg.message?.imageMessage?.caption
        || msg.message?.audioMessage || msg.message?.pttMessage)
      if (msg.key.id && processedIds.has(msg.key.id)) continue
      if (msg.key.id && msgHasContent) { processedIds.add(msg.key.id); setTimeout(() => processedIds.delete(msg.key.id), 60000) }

      // Filter fromMe messages — allow: self-chat and groups (owner writing in group)
      if (msg.key.fromMe) {
        const isGroup = msg.key.remoteJid?.endsWith('@g.us')
        const myJid   = (sock?.user?.id || '').replace(/:\d+@/, '@')
        const myLid   = (sock?.authState?.creds?.me?.lid || '').replace(/:\d+@/, '@')
        if (!isGroup && msg.key.remoteJid !== myJid && msg.key.remoteJid !== myLid) continue
      }

      if (msg.key.remoteJid?.endsWith('@g.us')) {
        const groupJid   = msg.key.remoteJid
        const groupText  = msg.message?.conversation || msg.message?.extendedTextMessage?.text || msg.message?.imageMessage?.caption || ''
        const groupImage = msg.message?.imageMessage ? msg : null
        const groupAudio = !!(msg.message?.audioMessage || msg.message?.pttMessage)
        if (!groupText.trim() && !groupImage && !groupAudio) continue

        // Transcribe audio in group (owner only — avoid running Whisper for every stranger's voice note)
        let groupIncomingText = groupText
        if (!groupIncomingText.trim() && groupAudio) {
          // Determine isOwner early for audio (need persona + allowFrom)
          const _p = loadPersona() || {}
          const _af = (_p.allowFrom || []).map(n => n.replace(/\s/g, ''))
          const _sp = (msg.key.participant || '').replace(/@.*/, '').replace(/:.*/, '')
          const _rp = (msg.key.participant || '').includes('@lid')
            ? (lidToPhone.get(_sp) || fromJid(msg.key.participant || ''))
            : fromJid(msg.key.participant || '')
          const _s10 = (n) => n.replace(/^\+/, '').slice(-10)
          const _isOwnerAudio = msg.key.fromMe
            || _af.length === 0
            || _af.some(n => _rp === n || _s10(_rp) === _s10(n))
          if (_isOwnerAudio) {
            console.log(`[Dexter] Group audio from owner — transcribing...`)
            const ap = await downloadAudio(msg)
            if (ap) {
              const tr = await transcribeAudio(ap)
              try { fs.unlinkSync(ap) } catch (_) {}
              if (tr) { groupIncomingText = tr; console.log(`[Dexter] Group audio transcribed: "${tr.substring(0,80)}"`) }
            }
          }
          if (!groupIncomingText.trim() && !groupImage) continue
        }

        const persona      = loadPersona() || {}
        const allowFrom    = (persona.allowFrom || []).map(n => n.replace(/\s/g, ''))
        const senderPart    = msg.key.participant || ''
        const senderRaw     = senderPart.replace(/@.*/, '').replace(/:.*/, '')
        const resolvedPhone = senderPart.includes('@lid')
          ? (lidToPhone.get(senderRaw) || fromJid(senderPart))
          : fromJid(senderPart)
        const suffix10 = (n) => n.replace(/^\+/, '').slice(-10)
        const groupAllowed = (persona.groups?.[groupJid]?.allowedMembers || [])
        const isOwner = msg.key.fromMe  // message sent by this device = owner
          || allowFrom.length === 0
          || allowFrom.some(n => resolvedPhone === n || suffix10(resolvedPhone) === suffix10(n))
          || groupAllowed.some(n => resolvedPhone === n || suffix10(resolvedPhone) === suffix10(n))
        console.log(`[Dexter] group — jid:${groupJid} sender:${senderPart} resolved:${resolvedPhone} isOwner:${isOwner} text:${groupIncomingText.substring(0,50)}`)

        // Owner commands in any group (no wake word needed)
        if (isOwner) {
          if (/^dexter\s+join$/i.test(groupIncomingText.trim())) {
            const groups = persona.allowedGroups || []
            console.log(`[Dexter] group join — already in list: ${groups.includes(groupJid)}`)
            if (!groups.includes(groupJid)) {
              persona.allowedGroups = [...groups, groupJid]
              try { savePersona(persona) } catch (e) { console.error('[Dexter] savePersona error:', e.message) }
              try {
                await sock.sendMessage(groupJid, { text: '✅ Dexter activado en este grupo.' })
                console.log(`[Dexter] group join — sent activation message`)
              } catch (e) { console.error('[Dexter] sendMessage error:', e.message) }
            }
            continue
          }
          if (/^dexter\s+leave$/i.test(groupIncomingText.trim())) {
            persona.allowedGroups = (persona.allowedGroups || []).filter(g => g !== groupJid)
            savePersona(persona)
            await sock.sendMessage(groupJid, { text: '👋 Dexter desactivado en este grupo.' })
            continue
          }

          // "dexter allow +521234567890" — grant owner-level access in this group to a member
          const allowMatch = groupIncomingText.match(/^dexter\s+allow\s+(\+?[\d\s\-().]+)/i)
          if (allowMatch) {
            const phone = '+' + allowMatch[1].replace(/[^0-9]/g, '')
            if (!persona.groups) persona.groups = {}
            if (!persona.groups[groupJid]) persona.groups[groupJid] = {}
            const members = persona.groups[groupJid].allowedMembers || []
            if (!members.some(n => n.replace(/[^0-9]/g, '').slice(-10) === phone.slice(-10))) {
              persona.groups[groupJid].allowedMembers = [...members, phone]
              savePersona(persona)
            }
            const sent = await sock.sendMessage(groupJid, { text: `✅ Acceso completo otorgado a ${phone}.` })
            if (sent?.key?.id) trackSentId(sent.key.id)
            continue
          }

          // "dexter deny +521234567890" — revoke owner-level access in this group
          const denyMatch = groupIncomingText.match(/^dexter\s+deny\s+(\+?[\d\s\-().]+)/i)
          if (denyMatch) {
            const phone = denyMatch[1].replace(/[^0-9]/g, '')
            if (persona.groups?.[groupJid]?.allowedMembers) {
              persona.groups[groupJid].allowedMembers = persona.groups[groupJid].allowedMembers
                .filter(n => n.replace(/[^0-9]/g, '').slice(-10) !== phone.slice(-10))
              savePersona(persona)
            }
            const sent = await sock.sendMessage(groupJid, { text: `✅ Acceso revocado.` })
            if (sent?.key?.id) trackSentId(sent.key.id)
            continue
          }

          // "dexter set [instrucción]" — persist a standing instruction for this group
          const setMatch = groupIncomingText.match(/^dexter\s+set\s+(.+)/i)
          if (setMatch) {
            const instruction = setMatch[1].trim()
            if (!persona.groups) persona.groups = {}
            if (!persona.groups[groupJid]) persona.groups[groupJid] = {}
            persona.groups[groupJid].instructions = [...(persona.groups[groupJid].instructions || []), instruction]
            savePersona(persona)
            const sent = await sock.sendMessage(groupJid, { text: '✅ Instrucción guardada.' })
            if (sent?.key?.id) trackSentId(sent.key.id)
            continue
          }

          // "dexter reset" — clear all custom config for this group (instructions, personality, allowed members)
          if (/^dexter\s+reset$/i.test(groupIncomingText.trim())) {
            if (persona.groups?.[groupJid]) {
              delete persona.groups[groupJid].instructions
              delete persona.groups[groupJid].personality
              delete persona.groups[groupJid].allowedMembers
              savePersona(persona)
            }
            const sent = await sock.sendMessage(groupJid, { text: '✅ Configuración del grupo reseteada.' })
            if (sent?.key?.id) trackSentId(sent.key.id)
            continue
          }
        }

        // Non-command group messages: only respond if group is allowed
        const allowedGroups = persona.allowedGroups || []
        if (!allowedGroups.includes(groupJid)) continue

        // "dexter eres [personalidad]" — anyone can set the group personality
        const eresMatch = groupIncomingText.match(/^dexter\s+eres\s+(.+)/i)
        if (eresMatch) {
          setGroupPersonality(groupJid, eresMatch[1].trim())
          const sent = await sock.sendMessage(groupJid, { text: '✅ Personalidad actualizada.' })
          if (sent?.key?.id) trackSentId(sent.key.id)
          continue
        }

        // Both owner and non-owner must use the wake word in groups.
        // This prevents Dexter from interrupting every message in the conversation.
        // Difference: owner gets full machine/file access, others get restricted access.
        const wakeWord = persona.wake_word !== undefined ? persona.wake_word : 'dexter'
        if (wakeWord && !new RegExp(wakeWord, 'i').test(groupIncomingText)) continue

        if (isOwner) {
          handleGroupChat(groupJid, groupIncomingText, true, groupImage).catch(e => console.error('[Dexter] group handler error:', e.message))
        } else {
          handleGroupChat(groupJid, groupIncomingText, false, groupImage).catch(e => console.error('[Dexter] group handler error:', e.message))
        }
        continue
      }

      const senderJid = msg.key.remoteJid
      const text = msg.message?.conversation
        || msg.message?.extendedTextMessage?.text
        || msg.message?.imageMessage?.caption
        || ''
      const hasImage = !!msg.message?.imageMessage
      const hasAudio = !!(msg.message?.audioMessage || msg.message?.pttMessage)

      // Skip if no text, no image, no audio
      if (!text.trim() && !hasImage && !hasAudio) continue

      // Transcribe audio messages before handling
      let incomingText = text
      if (!incomingText.trim() && hasAudio) {
        console.log(`[Dexter] Audio message received — transcribing with Whisper...`)
        const audioPath = await downloadAudio(msg)
        if (audioPath) {
          const transcript = await transcribeAudio(audioPath)
          try { fs.unlinkSync(audioPath) } catch (_) {}
          if (transcript) {
            incomingText = transcript
            console.log(`[Dexter] Audio transcribed: "${transcript.substring(0, 80)}"`)
          } else {
            console.warn('[Dexter] Whisper returned empty transcript')
          }
        }
        if (!incomingText.trim() && !hasImage) continue
      }

      const persona = loadPersona()
      const cfg = loadConfig()
      // allowFrom: persona takes priority, fallback to notifications.json
      const allowFrom = (persona?.allowFrom || cfg.whatsapp?.allowFrom || []).map(n => n.replace(/\s/g, ''))
      const senderRaw = senderJid.replace(/@.*/, '').replace(/:.*/, '') // raw without @domain and :device

      // Resolve @lid to actual phone (from contacts sync cache)
      const resolvedPhone = senderJid.includes('@lid')
        ? (lidToPhone.get(senderRaw) || fromJid(senderJid))
        : fromJid(senderJid)

      const isAllowed = allowFrom.length === 0
        || allowFrom.some(n => {
          const normalized = n.replace(/^\+/, '')
          const rPhone     = resolvedPhone.replace(/^\+/, '')
          // Suffix match (last 10 digits) handles country code variants like 52 vs 521
          const suffix = normalized.slice(-10)
          return rPhone === normalized
            || senderRaw === normalized
            || rPhone.endsWith(suffix)
            || senderRaw.endsWith(suffix)
        })

      console.log(`[Dexter] msg — jid:${senderJid} resolved:${resolvedPhone} allowed:${isAllowed}`)

      // @lid JIDs can't receive messages — resolve to @s.whatsapp.net for replies
      const replyJid = senderJid.includes('@lid')
        ? resolvedPhone.replace(/^\+/, '') + '@s.whatsapp.net'
        : senderJid

      if (isAllowed) {
        // "dexter reset history" — clear in-memory conversation history for this chat
        if (/^dexter\s+reset\s*(history|historial)?$/i.test(incomingText.trim())) {
          chatHistory.delete(replyJid)
          const sent = await sock.sendMessage(replyJid, { text: '✅ Historial borrado.' })
          if (sent?.key?.id) trackSentId(sent.key.id)
          continue
        }
        handleAllowedSender(replyJid, incomingText, hasImage ? msg : null).catch(e => console.error('[Dexter] allowed handler error:', e.message))
      } else {
        // Strangers: only respond if they explicitly mention the wake word (default: "dexter")
        const wakeWord = persona?.wake_word !== undefined ? persona.wake_word : 'dexter'
        if (wakeWord && !new RegExp(wakeWord, 'i').test(incomingText)) continue
        handleUnknownSender(replyJid, incomingText).catch(e => console.error('[Dexter] stranger handler error:', e.message))
      }
    } catch (e) { console.error('[Dexter] message loop error (non-fatal):', e.message, e.stack?.split('\n')[1]) } }
  })
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

const USE_QR = process.argv.includes('--qr') || process.env.WA_QR === '1'

// Prevent libsignal SessionErrors from crashing the process — these happen
// when decrypting old messages from history sync with missing session keys.
process.on('uncaughtException', (err) => {
  if (err.name === 'SessionError' || err.message?.includes('No sessions') || err.message?.includes('Bad MAC')) {
    console.warn('[Dexter] Ignored session decrypt error (old message):', err.message)
    return
  }
  console.error('[Dexter] Uncaught exception:', err)
  process.exit(1)
})

process.on('unhandledRejection', (reason) => {
  const msg = reason?.message || String(reason)
  if (msg.includes('No sessions') || msg.includes('Bad MAC') || msg.includes('SessionError')) {
    console.warn('[Dexter] Ignored session rejection (old message):', msg)
    return
  }
  console.error('[Dexter] Unhandled rejection:', reason)
})

console.log('[Dexter] Starting WhatsApp server...')
const myPhone = getMyPhone()
if (myPhone) console.log(`[Dexter] Phone: ${myPhone}`)
if (USE_QR) console.log('[Dexter] QR mode enabled — scan with WhatsApp to pair')

connect().catch(err => {
  console.error('[Dexter] Fatal error:', err.message)
  process.exit(1)
})
