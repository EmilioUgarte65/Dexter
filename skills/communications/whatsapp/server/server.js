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
  return '+' + jid.replace('@s.whatsapp.net', '').replace('@c.us', '')
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

  return `Sos el asistente de WhatsApp de ${name}.${about ? ` ${about}.` : ''}
Respondé los mensajes como si fueras ${name}, con un tono ${tone}.
Idioma: ${lang === 'es' ? 'español rioplatense' : lang}.
${avail ? `Disponibilidad: ${avail}.` : ''}
${rules ? `\nReglas importantes:\n${rules}` : ''}

IMPORTANTE:
- No des información personal, direcciones, documentos ni contraseñas.
- No hagas promesas de llamar, reunirte o pagar sin que ${name} lo confirme.
- Si alguien hace una pregunta que no podés responder con certeza, decí que ${name} le va a responder personalmente.
- Mantené las respuestas cortas, naturales, como un mensaje de WhatsApp real.
- No menciones que sos una IA ni un asistente automático a menos que te lo pregunten directamente.`
}

// ─── Persona responder ────────────────────────────────────────────────────────

async function handleUnknownSender(senderJid, incomingText) {
  const senderPhone = fromJid(senderJid)
  const persona = loadPersona()

  logMessage({ direction: 'in', from: senderPhone, text: incomingText, tier: 'restricted' })

  if (!persona) {
    const fallback = 'Hola, en este momento no puedo responder. Te escribo a la brevedad 👋'
    await sock.sendMessage(senderJid, { text: fallback })
    logMessage({ direction: 'out', to: senderPhone, text: fallback, tier: 'fallback' })
    return
  }

  // Fixed reply — no LLM needed
  if (persona.stranger_reply) {
    await sock.sendMessage(senderJid, { text: persona.stranger_reply })
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

async function handleAllowedSender(senderJid, incomingText) {
  const senderPhone = fromJid(senderJid)
  logMessage({ direction: 'in', from: senderPhone, text: incomingText, tier: 'allowed' })
  console.log(`[Dexter] Message from ${senderPhone} (allowed): ${incomingText.substring(0, 60)}`)
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
      keys: makeCacheableSignalKeyStore(state.keys, { level: () => {} }),
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
        console.log('│  → Ingresá el código de arriba           │')
        console.log('└─────────────────────────────────────────┘\n')
        waitingForPairing = true
        await waitForEnter('  ✅ Ingresaste el código en WhatsApp? Presioná Enter para continuar...\n')
        waitingForPairing = false
      } catch (e) {
        console.error('[Dexter] Pairing code error:', e.message)
      }
    }

    if (connection === 'open') {
      console.log('[Dexter] ✅ WhatsApp connected')
      isReady = true
      startHttpServer()
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

  // ─── Incoming messages ──────────────────────────────────────────────────────
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return

    for (const msg of messages) {
      if (msg.key.fromMe) continue
      if (msg.key.remoteJid === 'status@broadcast') continue

      const senderJid = msg.key.remoteJid
      const text = msg.message?.conversation
        || msg.message?.extendedTextMessage?.text
        || ''

      if (!text.trim()) continue

      const cfg = loadConfig()
      const allowFrom = cfg.whatsapp?.allowFrom || []
      const senderPhone = fromJid(senderJid)

      const isAllowed = allowFrom.length === 0
        || allowFrom.some(n => n.replace(/\s/g, '') === senderPhone)

      if (isAllowed) {
        await handleAllowedSender(senderJid, text)
      } else {
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
