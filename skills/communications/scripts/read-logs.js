#!/usr/bin/env node
/**
 * Dexter Log Reader — reads conversation logs filtered by contact or group
 *
 * Usage:
 *   node read-logs.js --platform whatsapp --contact +5218337587196
 *   node read-logs.js --platform whatsapp --group 120363425214480165@g.us
 *   node read-logs.js --platform telegram --contact 8601362723
 *   node read-logs.js --platform telegram --group -1001234567890
 *   node read-logs.js --platform whatsapp --contact +5218337587196 --limit 10
 *   node read-logs.js --platform whatsapp --contact +5218337587196 --today false
 *
 * Options:
 *   --platform   whatsapp | telegram (required)
 *   --contact    Filter by contact phone/userId (DM messages)
 *   --group      Filter by group ID
 *   --limit      Max messages to return (default: 20)
 *   --today      Only today's messages (default: true)
 */

const fs = require('fs')
const path = require('path')
const os = require('os')

// ─── Argument parsing ────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = {}
  for (let i = 2; i < argv.length; i++) {
    if (argv[i].startsWith('--') && i + 1 < argv.length) {
      const key = argv[i].slice(2)
      args[key] = argv[++i]
    }
  }
  return args
}

const args = parseArgs(process.argv)

if (!args.platform || !['whatsapp', 'telegram'].includes(args.platform)) {
  console.error('Error: --platform must be "whatsapp" or "telegram"')
  process.exit(1)
}

if (!args.contact && !args.group) {
  console.error('Error: must provide --contact or --group')
  process.exit(1)
}

const platform = args.platform
const contact  = args.contact || null
const group    = args.group || null
const limit    = parseInt(args.limit || '20', 10)
const todayOnly = args.today !== 'false'

// ─── Log file path ───────────────────────────────────────────────────────────

const logFile = path.join(os.homedir(), '.dexter', `${platform}-messages.jsonl`)

if (!fs.existsSync(logFile)) {
  console.log(`No log file found: ${logFile}`)
  process.exit(0)
}

// ─── Read and filter ─────────────────────────────────────────────────────────

const todayStr = new Date().toISOString().slice(0, 10) // YYYY-MM-DD

const raw = fs.readFileSync(logFile, 'utf8')
const lines = raw.split('\n').filter(l => l.trim())

const matched = []

for (const line of lines) {
  let entry
  try {
    entry = JSON.parse(line)
  } catch (_) {
    continue
  }

  // Date filter
  if (todayOnly && entry.ts) {
    const entryDate = entry.ts.slice(0, 10)
    if (entryDate !== todayStr) continue
  }

  // Contact filter: match from or to fields (handles phone numbers and user IDs)
  if (contact) {
    const from = String(entry.from || '')
    const to   = String(entry.to || '')
    const chatId = String(entry.chatId || '')
    // Normalize: strip + and compare last 10 digits for phone numbers
    const normalize = (n) => n.replace(/^\+/, '').slice(-10)
    const cNorm = normalize(contact)
    const match = normalize(from) === cNorm
      || normalize(to) === cNorm
      || normalize(chatId) === cNorm
      || from === contact
      || to === contact
      || chatId === contact
    if (!match) continue
  }

  // Group filter: match chatId field
  if (group) {
    const chatId = String(entry.chatId || entry.to || '')
    if (chatId !== group && !chatId.includes(group)) continue
    // Skip if this is a DM log entry that happens to match
    if (entry.direction === 'in' && !entry.chatId) continue
  }

  matched.push(entry)
}

// ─── Output ──────────────────────────────────────────────────────────────────

// Take the last N messages (most recent)
const output = matched.slice(-limit)

if (output.length === 0) {
  const scope = contact ? `contact ${contact}` : `group ${group}`
  const period = todayOnly ? 'today' : 'all time'
  console.log(`No messages found for ${scope} (${period})`)
  process.exit(0)
}

for (const entry of output) {
  const time = entry.ts ? new Date(entry.ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '??:??'
  const direction = entry.direction
  const text = entry.text || ''

  if (direction === 'in') {
    const sender = entry.from || entry.username || 'User'
    console.log(`[${time}] ${sender}: ${text}`)
  } else if (direction === 'out') {
    console.log(`[${time}] Dexter: ${text}`)
  }
}
