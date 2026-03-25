#!/usr/bin/env node
/**
 * Dexter WhatsApp Server — Baileys HTTP bridge
 *
 * Works with any regular WhatsApp number. No Meta Business account required.
 * First run shows a QR code — scan with phone → paired forever.
 * Credentials saved to ~/.dexter/whatsapp/ (persistent across restarts).
 *
 * API:
 *   POST /api/sendText   { "to": "+1234567890", "text": "Hello" }
 *   GET  /status         { "ok": true, "ready": true }
 *
 * Usage:
 *   node server.js            # default port 3000
 *   WA_PORT=3001 node server.js
 */

const { default: makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys')
const { Boom } = require('@hapi/boom')
const http = require('http')
const os = require('os')
const path = require('path')
const qrcode = require('qrcode-terminal')

const AUTH_DIR = path.join(os.homedir(), '.dexter', 'whatsapp')
const PORT = parseInt(process.env.WA_PORT || '3000', 10)

let sock = null
let isReady = false
let httpStarted = false

// ─── Normalize phone → WhatsApp JID ──────────────────────────────────────────

function toJid(phone) {
  const digits = phone.replace(/[^0-9]/g, '')
  return digits + '@s.whatsapp.net'
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
          await sock.sendMessage(toJid(to), { text })
          res.writeHead(200, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ ok: true }))
        } catch (e) {
          res.writeHead(500, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ ok: false, error: e.message }))
        }
      })

    } else if (req.method === 'GET' && req.url === '/status') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ ok: true, ready: isReady }))

    } else {
      res.writeHead(404)
      res.end()
    }
  })

  server.listen(PORT, '127.0.0.1', () => {
    console.log(`[Dexter] WhatsApp API ready → http://localhost:${PORT}`)
    console.log(`[Dexter] Send: POST /api/sendText  { "to": "+1234567890", "text": "Hola" }`)
  })
}

// ─── Baileys socket ───────────────────────────────────────────────────────────

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)

  sock = makeWASocket({
    auth: state,
    printQRInTerminal: false,
    browser: ['Dexter', 'Desktop', '1.0'],
    syncFullHistory: false,
    markOnlineOnConnect: false,
  })

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      console.log('\n[Dexter] Scan this QR code with your phone:\n')
      qrcode.generate(qr, { small: true })
      console.log('\n  WhatsApp → Settings → Linked Devices → Link a Device\n')
    }

    if (connection === 'open') {
      console.log('[Dexter] ✅ WhatsApp connected')
      isReady = true
      startHttpServer()
    }

    if (connection === 'close') {
      isReady = false
      const statusCode = new Boom(lastDisconnect?.error)?.output?.statusCode
      const loggedOut = statusCode === DisconnectReason.loggedOut

      if (loggedOut) {
        console.log('[Dexter] Logged out. Delete ~/.dexter/whatsapp/ and restart to re-pair.')
      } else {
        console.log('[Dexter] Disconnected — reconnecting...')
        connect()
      }
    }
  })
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

connect().catch(err => {
  console.error('[Dexter] Fatal error:', err.message)
  process.exit(1)
})
