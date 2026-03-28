#!/usr/bin/env node
/**
 * Dexter WhatsApp Server — Baileys HTTP bridge + personal assistant
 *
 * Two-tier access:
 *   - Numbers in allowFrom → full Dexter capabilities (outbound only, agent handles)
 *   - Unknown numbers     → restricted persona responder (AI replies as you)
 *
 * Pairing: phone number pairing (no QR needed — works headless)
 *   WA_PHONE=+528337587196 node server.js
 *   Or set "allowFrom": ["+52..."] in ~/.dexter/whatsapp-persona.json
 *
 * Persona config: ~/.dexter/whatsapp-persona.json
 * Notifications:  ~/.dexter/notifications.json
 * Credentials:    ~/.dexter/whatsapp/
 *
 * API:
 *   POST /api/sendText   { "to": "+1234567890", "text": "Hello" }
 *   GET  /status
 *
 * Usage:
 *   WA_PHONE=+528337587196 node server.js    # port 3000
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

const AUTH_DIR    = path.join(os.homedir(), '.dexter', 'whatsapp')
const CONFIG_PATH = path.join(os.homedir(), '.dexter', 'notifications.json')
const PERSONA_PATH = path.join(os.homedir(), '.dexter', 'whatsapp-persona.json')
const LOG_PATH    = path.join(os.homedir(), '.dexter', 'whatsapp-messages.jsonl')
const PORT = parseInt(process.env.WA_PORT || '3000', 10)

let sock = null
let isReady = false
let httpStarted = false
let pairingRequested = false
let waitingForPairing = false
const lidToPhone   = new Map()  // LID (raw) → "+phone" — populated from contacts.upsert
const sentMsgIds   = new Set()  // IDs of messages Dexter sent — skip on echo to prevent loops

// Per-chat conversation history — keeps the last N turns so Claude has context.
// Key: senderJid, Value: Array of { role: 'user'|'assistant', text: string }
const chatHistory  = new Map()
const HISTORY_LIMIT = 20  // max turns to keep per chat

function waitForEnter(prompt) {
  return new Promise(resolve => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
    rl.question(prompt, () => { rl.close(); resolve() })
  })
}

function waitForCredsSave(ms = 5000) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

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
  return '+' + jid.replace(/@s\.whatsapp\.net$/, '').replace(/@c\.us$/, '').replace(/@lid$/, '')
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

  // Base rules applied to ALL group messages — prevents Claude from leaking
  // coding/terminal context even when running from the Dexter project directory.
  const baseRules = `
CONTEXTO: Estás respondiendo mensajes en un grupo de WhatsApp. NO eres un asistente de código ni de terminal.
REGLAS ABSOLUTAS (nunca las rompas):
- Mensajes cortos y naturales, como en un chat real. Sin listas, sin markdown, sin títulos.
- Responde en el mismo idioma que te hablen.
- NUNCA menciones terminales, archivos, código, directorios, proyectos de software ni herramientas de desarrollo.
- NUNCA digas que no puedes hacer algo porque "no tienes acceso" — simplemente responde como una persona.
- NO menciones que eres una IA a menos que te lo pregunten directamente.`

  if (isOwner) {
    // Owner gets full Dexter capabilities (machine, files, code) AND group context.
    // baseRules NOT applied — owner is allowed to ask about the machine/files.
    return `Eres Dexter, el asistente personal de ${ownerName}. Estás respondiendo en un grupo de WhatsApp.
- Tienes acceso completo: archivos, terminal, código, búsquedas, lo que necesite.
- Responde en el mismo idioma que te hablen.
- Mensajes concisos — estás en un chat, no en una terminal.
- NO reveles información privada de ${ownerName} (contraseñas, datos personales sensibles) a otros miembros del grupo.
- Mantén el contexto de la conversación del grupo.`
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
        if (sent?.key?.id) sentMsgIds.add(sent.key.id)
        logMessage({ direction: 'out', to: groupJid, text: response, tier: 'group' })
      }
      return
    }
  }

  const useEngram = engramAvailable()
  let prompt, args

  if (useEngram) {
    // Engram mode: merge group persona system prompt with Engram memory protocol
    const engramPrompt = buildEngramSystemPrompt(groupJid, true)
    const combinedSystemPrompt = `${systemPrompt}\n\n${engramPrompt}`
    prompt = text
    args = ['-p', prompt, '--system-prompt', combinedSystemPrompt, '--dangerously-skip-permissions']
  } else {
    // Fallback: in-RAM history + group persona system prompt
    const history = chatHistory.get(groupJid) || []
    prompt = buildPromptWithHistory(history, text)
    appendHistory(groupJid, 'user', text)
    args = ['-p', prompt, '--system-prompt', systemPrompt, '--allowedTools', '', '--dangerously-skip-permissions']
  }

  const spawnEnv = { ...process.env }
  delete spawnEnv.CLAUDECODE

  // Owner messages run from Dexter root so Claude has full project context.
  // Non-owner (group chat) runs from home to avoid leaking coding/project context
  // into what should be a casual WhatsApp conversation.
  const cwd = isOwner ? path.resolve(__dirname, '../../../..') : os.homedir()

  const response = await new Promise((resolve) => {
    let stdout = ''
    let stderr = ''
    const child = spawn(cli, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      cwd,
      env: spawnEnv,
    })
    const timer = setTimeout(() => { child.kill('SIGTERM'); resolve(null) }, 60000)
    child.stdout.on('data', d => { stdout += d.toString() })
    child.stderr.on('data', d => { stderr += d.toString() })
    child.on('close', (code) => {
      clearTimeout(timer)
      resolve(code === 0 && stdout.trim() ? stdout.trim() : null)
    })
    child.on('error', () => { clearTimeout(timer); resolve(null) })
  })

  if (response) {
    if (!useEngram) appendHistory(groupJid, 'assistant', response)
    const sent = await sock.sendMessage(groupJid, { text: response })
    if (sent?.key?.id) sentMsgIds.add(sent.key.id)
    logMessage({ direction: 'out', to: groupJid, text: response, tier: 'group' })
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
    if (sent?.key?.id) sentMsgIds.add(sent.key.id)
    logMessage({ direction: 'out', to: senderPhone, text: fallback, tier: 'fallback' })
    return
  }

  // Fixed reply — no LLM needed
  if (persona.stranger_reply) {
    const sent = await sock.sendMessage(senderJid, { text: persona.stranger_reply })
    if (sent?.key?.id) sentMsgIds.add(sent.key.id)
    logMessage({ direction: 'out', to: senderPhone, text: persona.stranger_reply, tier: 'persona-fixed' })
    return
  }

  try {
    const reply = await callLLM(persona, senderPhone, incomingText)
    if (reply) {
      await sock.sendMessage(senderJid, { text: reply })
      logMessage({ direction: 'out', to: senderPhone, text: reply, tier: 'persona' })
    } else {
      const fallback = persona.fallback_message || 'Hola! En este momento no puedo responder, te escribo pronto 👋'
      await sock.sendMessage(senderJid, { text: fallback })
      logMessage({ direction: 'out', to: senderPhone, text: fallback, tier: 'fallback' })
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

// Runs the LLM CLI with an image attachment.
// Cleans up the temp file after the call.
function runLLMCliWithImage(cli, prompt, imagePath) {
  return new Promise((resolve) => {
    let stdout = '', stderr = ''
    const dexterRoot = path.resolve(__dirname, '../../../..')
    const spawnEnv = { ...process.env }
    delete spawnEnv.CLAUDECODE
    const args = ['-p', prompt, '--image', imagePath, '--dangerously-skip-permissions']
    const child = spawn(cli, args, { stdio: ['ignore', 'pipe', 'pipe'], cwd: dexterRoot, env: spawnEnv })
    const timer = setTimeout(() => { child.kill('SIGTERM'); console.error('[Dexter] Image LLM timed out'); resolve(null) }, 120000)
    child.stdout.on('data', d => { stdout += d.toString() })
    child.stderr.on('data', d => { stderr += d.toString() })
    child.on('close', (code) => {
      clearTimeout(timer)
      try { fs.unlinkSync(imagePath) } catch (_) {}  // clean up temp file
      if (code === 0 && stdout.trim()) { resolve(stdout.trim()) }
      else { if (stderr) console.error('[Dexter] Image LLM stderr:', stderr.substring(0, 300)); resolve(null) }
    })
    child.on('error', (err) => { clearTimeout(timer); console.error('[Dexter] Image spawn error:', err.message); resolve(null) })
  })
}

function runLLMCli(cli, message) {
  return new Promise((resolve) => {
    let stdout = ''
    let stderr = ''
    // Run from Dexter project root so Claude picks up DEXTER.md + CLAUDE.md context.
    // Unset CLAUDECODE env var to avoid "nested session" error when the server
    // is started from inside an active Claude Code / Antigravity session.
    const dexterRoot = path.resolve(__dirname, '../../../..')
    const spawnEnv = { ...process.env }
    delete spawnEnv.CLAUDECODE
    const child = spawn(cli, ['-p', message], {
      stdio: ['ignore', 'pipe', 'pipe'],
      cwd: dexterRoot,
      env: spawnEnv,
    })

    const timer = setTimeout(() => {
      child.kill('SIGTERM')
      console.error('[Dexter] LLM CLI timed out after 120s')
      resolve(null)
    }, 120000)

    child.stdout.on('data', d => { stdout += d.toString() })
    child.stderr.on('data', d => { stderr += d.toString() })

    child.on('close', (code) => {
      clearTimeout(timer)
      if (code === 0 && stdout.trim()) {
        resolve(stdout.trim())
      } else {
        if (stderr) console.error(`[Dexter] LLM CLI stderr:`, stderr.substring(0, 300))
        resolve(null)
      }
    })

    child.on('error', (err) => {
      clearTimeout(timer)
      console.error('[Dexter] LLM CLI spawn error:', err.message)
      resolve(null)
    })
  })
}

// ─── Engram availability check ────────────────────────────────────────────────

function engramAvailable() {
  // Engram is available if the binary exists in PATH
  const isWin = process.platform === 'win32'
  const r = spawnSync(isWin ? 'where' : 'which', ['engram'], { encoding: 'utf8', timeout: 3000 })
  return r.status === 0 && !!r.stdout.trim()
}

// Builds a system prompt that instructs Claude to use Engram for persistent
// memory across WhatsApp conversations. Claude will mem_search on start and
// mem_save after responding — no raw history needed in the prompt.
function buildEngramSystemPrompt(contactId, isGroup) {
  const scope = isGroup ? 'group' : 'contact'
  return `You are Dexter, a personal AI assistant responding via WhatsApp.
You have access to Engram persistent memory tools (mem_search, mem_save, mem_context).

MEMORY PROTOCOL — follow this on EVERY message:
1. START: Call mem_search with query "${contactId}" and project "dexter-whatsapp" to load conversation context for this ${scope}.
2. RESPOND: Use that context to give a coherent, continuous response. Never act like this is the first message if memory exists.
3. END: Call mem_save to save a brief summary of this interaction (what was asked, what you did/answered) with project "dexter-whatsapp", topic_key "wa/${contactId}".

This gives you persistent memory across server restarts — the conversation never loses its thread.
If mem_search returns nothing, this is genuinely the first interaction with this ${scope}.`
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
  let prompt, args

  if (useEngram) {
    // Engram mode: Claude manages its own memory via mem_search/mem_save.
    // No raw history in the prompt — token-efficient and persistent across restarts.
    // --dangerously-skip-permissions: no interactive prompts in headless mode.
    const systemPrompt = buildEngramSystemPrompt(senderPhone, false)
    prompt = incomingText
    args = ['-p', prompt, '--system-prompt', systemPrompt, '--dangerously-skip-permissions']
    console.log(`[Dexter] Engram mode — persistent memory active for ${senderPhone}`)
  } else {
    // Fallback: in-RAM conversation history (lost on server restart).
    // --dangerously-skip-permissions: no interactive prompts in headless mode.
    const history = chatHistory.get(senderJid) || []
    prompt = buildPromptWithHistory(history, incomingText)
    appendHistory(senderJid, 'user', incomingText)
    args = ['-p', prompt, '--dangerously-skip-permissions']
    console.log(`[Dexter] RAM history mode (Engram not found) for ${senderPhone}`)
  }

  console.log(`[Dexter] Thinking with ${cli}...`)
  try {
    // If an image was sent, download it and pass it to Claude directly.
    // Skips Engram/RAM prompt building — image + caption is the full context.
    if (imageMsg) {
      const imagePath = await downloadImage(imageMsg)
      if (imagePath) {
        const imagePrompt = incomingText.trim() || 'Describe esta imagen.'
        const response = await runLLMCliWithImage(cli, imagePrompt, imagePath)
        if (response) {
          const sent = await sock.sendMessage(senderJid, { text: response })
          if (sent?.key?.id) sentMsgIds.add(sent.key.id)
          logMessage({ direction: 'out', to: senderPhone, text: response, tier: 'allowed-llm' })
          console.log(`[Dexter] → ${senderPhone}: ${response.substring(0, 80)}`)
        } else {
          console.warn('[Dexter] LLM returned empty response for image')
        }
        return
      }
    }

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
      if (!useEngram) appendHistory(senderJid, 'assistant', response)
      const sent = await sock.sendMessage(senderJid, { text: response })
      if (sent?.key?.id) sentMsgIds.add(sent.key.id)
      logMessage({ direction: 'out', to: senderPhone, text: response, tier: 'allowed-llm' })
      console.log(`[Dexter] → ${senderPhone}: ${response.substring(0, 80)}`)
    } else {
      console.warn('[Dexter] LLM returned empty response')
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
  const { version } = await fetchLatestBaileysVersion()

  sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, { trace: ()=>{}, debug: ()=>{}, info: ()=>{}, warn: ()=>{}, error: ()=>{}, fatal: ()=>{}, child: ()=>({ trace: ()=>{}, debug: ()=>{}, info: ()=>{}, warn: ()=>{}, error: ()=>{}, fatal: ()=>{} }) }),
    },
    printQRInTerminal: false,
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

  sock.ev.on('connection.update', async ({ connection, lastDisconnect, isNewLogin }) => {

    // ── Phone number pairing (headless — no QR) ──────────────────────────────
    if (!sock.authState.creds.registered && !pairingRequested) {
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

    for (const msg of messages) {
      console.log(`[Dexter] raw — remoteJid:${msg.key.remoteJid} fromMe:${msg.key.fromMe} hasText:${!!(msg.message?.conversation || msg.message?.extendedTextMessage?.text)}`)

      if (msg.key.remoteJid === 'status@broadcast') continue

      // Skip messages Dexter sent (prevents infinite loop on echo)
      if (msg.key.id && sentMsgIds.has(msg.key.id)) { sentMsgIds.delete(msg.key.id); continue }

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
        if (!groupText.trim() && !groupImage) continue

        const persona      = loadPersona() || {}
        const allowFrom    = (persona.allowFrom || []).map(n => n.replace(/\s/g, ''))
        const senderPart    = msg.key.participant || ''
        const senderRaw     = senderPart.replace(/@.*/, '').replace(/:.*/, '')
        const resolvedPhone = senderPart.includes('@lid')
          ? (lidToPhone.get(senderRaw) || fromJid(senderPart))
          : fromJid(senderPart)
        const suffix10 = (n) => n.replace(/^\+/, '').slice(-10)
        const isOwner = msg.key.fromMe  // message sent by this device = owner
          || allowFrom.length === 0
          || allowFrom.some(n => resolvedPhone === n || suffix10(resolvedPhone) === suffix10(n))

        // Owner commands in any group (no wake word needed)
        if (isOwner) {
          if (/^dexter\s+join$/i.test(groupText.trim())) {
            const groups = persona.allowedGroups || []
            if (!groups.includes(groupJid)) {
              persona.allowedGroups = [...groups, groupJid]
              savePersona(persona)
              await sock.sendMessage(groupJid, { text: '✅ Dexter activado en este grupo.' })
            }
            continue
          }
          if (/^dexter\s+leave$/i.test(groupText.trim())) {
            // Only removes the group from allowedGroups — Dexter stops responding
            // but your number stays in the group.
            persona.allowedGroups = (persona.allowedGroups || []).filter(g => g !== groupJid)
            savePersona(persona)
            await sock.sendMessage(groupJid, { text: '👋 Dexter desactivado en este grupo.' })
            continue
          }
        }

        // Non-command group messages: only respond if group is allowed
        const allowedGroups = persona.allowedGroups || []
        if (!allowedGroups.includes(groupJid)) continue

        // "dexter eres [personalidad]" — anyone can set the group personality
        const eresMatch = groupText.match(/^dexter\s+eres\s+(.+)/i)
        if (eresMatch) {
          setGroupPersonality(groupJid, eresMatch[1].trim())
          const sent = await sock.sendMessage(groupJid, { text: '✅ Personalidad actualizada.' })
          if (sent?.key?.id) sentMsgIds.add(sent.key.id)
          continue
        }

        // Both owner and non-owner must use the wake word in groups.
        // This prevents Dexter from interrupting every message in the conversation.
        // Difference: owner gets full machine/file access, others get restricted access.
        const wakeWord = persona.wake_word !== undefined ? persona.wake_word : 'dexter'
        if (wakeWord && !new RegExp(wakeWord, 'i').test(groupText)) continue

        if (isOwner) {
          await handleGroupChat(groupJid, groupText, true, groupImage)
        } else {
          await handleGroupChat(groupJid, groupText, false, groupImage)
        }
        continue
      }

      const senderJid = msg.key.remoteJid
      const text = msg.message?.conversation
        || msg.message?.extendedTextMessage?.text
        || msg.message?.imageMessage?.caption
        || ''
      const hasImage = !!msg.message?.imageMessage

      // Skip if no text and no image
      if (!text.trim() && !hasImage) continue

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

      if (isAllowed) {
        await handleAllowedSender(senderJid, text, hasImage ? msg : null)
      } else {
        // Strangers: only respond if they explicitly mention the wake word (default: "dexter")
        const wakeWord = persona?.wake_word !== undefined ? persona.wake_word : 'dexter'
        if (wakeWord && !new RegExp(wakeWord, 'i').test(text)) continue
        await handleUnknownSender(senderJid, text)
      }
    }
  })
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

console.log('[Dexter] Starting WhatsApp server...')
const myPhone = getMyPhone()
if (myPhone) console.log(`[Dexter] Phone: ${myPhone}`)

connect().catch(err => {
  console.error('[Dexter] Fatal error:', err.message)
  process.exit(1)
})
