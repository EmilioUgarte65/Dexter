# Dexter Installer — Windows (PowerShell 5+)
# Usage: .\install.ps1 [-Agent claude-code|opencode|codex|cursor|gemini|vscode] [-DryRun]
[CmdletBinding()]
param(
  [string]$Agent = "",
  [switch]$DryRun
)

$DexterVersion = "1.0.0"
$DexterSourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupTimestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = "$env:USERPROFILE\.dexter-backup\$BackupTimestamp"

# ─── Helpers ───────────────────────────────────────────────────────────────────
function Info    { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Cyan }
function Success { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Green }
function Warn    { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Yellow }
function Err     { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Red -BackgroundColor Black }

# ─── OS / WSL2 detection ───────────────────────────────────────────────────────
function Detect-WSL2 {
  try {
    $wsl = wsl --status 2>&1
    return ($wsl -match "WSL 2" -or $wsl -match "Windows Subsystem for Linux")
  } catch {
    return $false
  }
}

# ─── Agent detection ───────────────────────────────────────────────────────────
function Detect-Agent {
  if ($Agent) { return $Agent }

  $appData = $env:APPDATA
  # Claude Code CLI uses ~/.claude (USERPROFILE), not %APPDATA%\Claude
  if (Test-Path "$env:USERPROFILE\.claude") { return "claude-code" }
  if (Test-Path "$appData\Claude") { return "claude-code" }
  if (Test-Path "$appData\OpenCode") { return "opencode" }
  if (Test-Path "$env:USERPROFILE\.codex") { return "codex" }
  if (Test-Path "$appData\Cursor") { return "cursor" }
  if (Test-Path "$env:USERPROFILE\.gemini") { return "gemini" }
  if (Get-Command "code" -ErrorAction SilentlyContinue) { return "vscode" }
  return ""
}

# ─── Agent paths (Windows equivalents) ────────────────────────────────────────
function Get-AgentPaths {
  param([string]$AgentName)
  $appData = $env:APPDATA
  $home    = $env:USERPROFILE

  switch ($AgentName) {
    "claude-code" {
      # Claude Code CLI reads config from ~/.claude (USERPROFILE), not %APPDATA%\Claude
      return @{
        ConfigDir    = "$home\.claude"
        PromptFile   = "$home\.claude\CLAUDE.md"
        SkillsDir    = "$home\.claude\skills"
        SettingsFile = "$home\.claude\settings.json"
        McpDir       = "$home\.claude\mcp"
        Strategy     = "MarkdownSections"
        McpStrategy  = "SeparateMCPFiles"
      }
    }
    "opencode" {
      return @{
        ConfigDir    = "$appData\OpenCode"
        PromptFile   = "$appData\OpenCode\AGENTS.md"
        SkillsDir    = "$appData\OpenCode\skills"
        SettingsFile = "$appData\OpenCode\config.json"
        McpDir       = ""
        Strategy     = "FileReplace"
        McpStrategy  = "JSONMerge"
      }
    }
    "codex" {
      return @{
        ConfigDir    = "$home\.codex"
        PromptFile   = "$home\.codex\instructions.md"
        SkillsDir    = "$home\.codex\skills"
        SettingsFile = "$home\.codex\config.toml"
        McpDir       = ""
        Strategy     = "AppendToFile"
        McpStrategy  = "TOMLFile"
      }
    }
    "cursor" {
      return @{
        ConfigDir    = "$appData\Cursor"
        PromptFile   = "$home\.cursorrules"
        SkillsDir    = "$appData\Cursor\skills"
        SettingsFile = "$appData\Cursor\mcp.json"
        McpDir       = ""
        Strategy     = "AppendToFile"
        McpStrategy  = "MCPConfigFile"
      }
    }
    "gemini" {
      return @{
        ConfigDir    = "$home\.gemini"
        PromptFile   = "$home\.gemini\GEMINI.md"
        SkillsDir    = "$home\.gemini\skills"
        SettingsFile = "$home\.gemini\settings.json"
        McpDir       = ""
        Strategy     = "AppendToFile"
        McpStrategy  = "JSONMerge"
      }
    }
    "vscode" {
      return @{
        ConfigDir    = "$appData\Code\User"
        PromptFile   = "$home\.github\copilot-instructions.md"
        SkillsDir    = "$appData\Code\User\dexter-skills"
        SettingsFile = "$appData\Code\User\settings.json"
        McpDir       = ""
        Strategy     = "AppendToFile"
        McpStrategy  = "MCPConfigFile"
      }
    }
    default {
      Err "Unknown agent: $AgentName"
      exit 1
    }
  }
}

# ─── Backup ────────────────────────────────────────────────────────────────────
function Backup-Files {
  param([hashtable]$Paths)
  Info "Creating backup at $BackupDir ..."
  if ($DryRun) { Info "[dry-run] Would backup to $BackupDir"; return }

  New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

  $manifest = @{ version = "1"; timestamp = (Get-Date -Format "o"); files = @() }

  foreach ($file in @($Paths.PromptFile, $Paths.SettingsFile)) {
    if (Test-Path $file) {
      $rel = $file -replace [regex]::Escape($env:USERPROFILE), "~"
      $sha256 = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
      $destDir = Join-Path $BackupDir (Split-Path -Parent $file)
      New-Item -ItemType Directory -Force -Path $destDir | Out-Null
      Copy-Item $file $destDir
      $manifest.files += @{ path = $rel; sha256 = $sha256 }
      Success "  Backed up: $rel"
    }
  }

  $manifest | ConvertTo-Json -Depth 5 | Set-Content "$BackupDir\manifest.json"
  Success "Backup complete: $BackupDir"
}

# ─── Inject system prompt ─────────────────────────────────────────────────────
function Inject-SystemPrompt {
  param([hashtable]$Paths)
  $target   = $Paths.PromptFile
  $strategy = $Paths.Strategy
  $content  = Get-Content "$DexterSourceDir\DEXTER.md" -Raw

  Info "Injecting Dexter config ($strategy) into: $target"
  if ($DryRun) { Info "[dry-run] Would inject into $target"; return }

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null

  switch ($strategy) {
    "MarkdownSections" {
      if ((Test-Path $target) -and (Select-String -Path $target -Pattern "<!-- dexter:core -->" -Quiet)) {
        Warn "Dexter already present in $target — updating block..."
        # Replace existing block
        $existing = Get-Content $target -Raw
        $newContent = $existing -replace "<!-- dexter:core -->[\s\S]*?<!-- /dexter:core -->", $content
        Set-Content $target $newContent
        Success "Updated Dexter block in $target"
      } else {
        Add-Content $target "`n$content`n"
        Success "Appended Dexter block to $target"
      }
    }
    "FileReplace" {
      Copy-Item "$DexterSourceDir\SOUL.md" $target -Force
      Success "Installed SOUL.md as $target"
    }
    "AppendToFile" {
      if (-not (Test-Path $target)) { New-Item -ItemType File -Force -Path $target | Out-Null }
      if (-not (Select-String -Path $target -Pattern "<!-- dexter:core -->" -Quiet)) {
        Add-Content $target "`n<!-- Dexter v$DexterVersion -->`n$content"
        Success "Appended Dexter config to $target"
      } else {
        Warn "Dexter already present in $target — skipping"
      }
    }
  }
}

# ─── Copy skills ───────────────────────────────────────────────────────────────
function Copy-Skills {
  param([string]$SkillsDir)
  Info "Installing skills to $SkillsDir ..."
  if ($DryRun) { Info "[dry-run] Would copy skills to $SkillsDir"; return }

  New-Item -ItemType Directory -Force -Path "$SkillsDir\_shared" | Out-Null
  Copy-Item "$DexterSourceDir\skills\_shared\*.md" "$SkillsDir\_shared\" -ErrorAction SilentlyContinue
  Copy-Item "$DexterSourceDir\CAPABILITIES.md" "$SkillsDir\CAPABILITIES.md"

  Get-ChildItem "$DexterSourceDir\skills" -Directory | Where-Object { $_.Name -notin @("_shared", "sonoscli") } | ForEach-Object {
    Copy-Item $_.FullName "$SkillsDir\$($_.Name)" -Recurse -Force
    Success "  Installed bundle: $($_.Name)"
  }

  Success "Skills installed"
}

# ─── Configure MCPs ────────────────────────────────────────────────────────────
function Configure-MCPs {
  param([hashtable]$Paths, [string]$AgentName)
  $strategy = $Paths.McpStrategy

  Info "Configuring MCPs (strategy: $strategy) ..."
  if ($DryRun) { Info "[dry-run] Would configure MCPs"; return }

  switch ($strategy) {
    "SeparateMCPFiles" {
      $mcpDir = $Paths.McpDir
      if ($mcpDir) {
        New-Item -ItemType Directory -Force -Path $mcpDir | Out-Null
        Copy-Item "$DexterSourceDir\mcp\engram.json"  "$mcpDir\engram.json"
        Copy-Item "$DexterSourceDir\mcp\context7.json" "$mcpDir\context7.json"
        Success "  MCP files installed to $mcpDir"
      }
    }
    "JSONMerge" {
      $settingsFile = $Paths.SettingsFile
      if (Get-Command node -ErrorAction SilentlyContinue) {
        node -e "
          const fs=require('fs');
          const s=fs.existsSync('$settingsFile')?JSON.parse(fs.readFileSync('$settingsFile','utf8')):{};
          s.mcpServers=s.mcpServers||{};
          s.mcpServers.engram={command:'engram',args:['mcp','--tools=agent']};
          s.mcpServers.context7={command:'npx',args:['-y','@upstash/context7-mcp']};
          require('fs').mkdirSync(require('path').dirname('$settingsFile'),{recursive:true});
          fs.writeFileSync('$settingsFile',JSON.stringify(s,null,2));
        "
        Success "  MCPs merged into $settingsFile"
      } else {
        Warn "  Node.js not found — manually add MCPs to $settingsFile"
      }
    }
    "TOMLFile" {
      $tomlAppend = @'

# Dexter MCP servers
[mcp.engram]
command = "engram"
args = ["mcp", "--tools=agent"]

[mcp.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]
'@
      Add-Content $Paths.SettingsFile $tomlAppend
      Success ("  MCPs appended to " + $Paths.SettingsFile)
    }
    "MCPConfigFile" {
      $mcpConfig = @{
        mcpServers = @{
          engram   = @{ command = "engram"; args = @("mcp", "--tools=agent") }
          context7 = @{ command = "npx"; args = @("-y", "@upstash/context7-mcp") }
        }
      }
      $mcpConfig | ConvertTo-Json -Depth 5 | Set-Content $Paths.SettingsFile
      Success "  MCP config written to $($Paths.SettingsFile)"
    }
  }
}

# ─── Dependency installer ──────────────────────────────────────────────────────
function Install-Dependencies {
  if ($DryRun) { Info "[dry-run] Would install Node.js and Engram"; return }

  # Node.js — required for WhatsApp server, MCP JSON merging, and npm packages
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Info "Installing Node.js (required for WhatsApp server and MCP tooling)..."
    try {
      winget install OpenJS.NodeJS --silent --accept-package-agreements --accept-source-agreements
      $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                  [System.Environment]::GetEnvironmentVariable("Path","User")
      if (Get-Command node -ErrorAction SilentlyContinue) {
        Success "  Node.js installed: $(node --version)"
      } else {
        Warn "  Node.js installed but not yet in PATH — restart your terminal if needed."
      }
    } catch {
      Warn "  Could not install Node.js via winget. Install manually: https://nodejs.org"
    }
  } else {
    Success "  Node.js already installed: $(node --version)"
  }

  # Engram — persistent cross-session memory (SQLite + FTS5 MCP server)
  if (-not (Get-Command engram -ErrorAction SilentlyContinue)) {
    Info "Installing Engram (persistent memory for Dexter — required for cross-session context)..."
    $installed = $false
    try {
      winget install engram --silent --accept-package-agreements --accept-source-agreements
      $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                  [System.Environment]::GetEnvironmentVariable("Path","User")
      if (Get-Command engram -ErrorAction SilentlyContinue) {
        Success "  Engram installed: $(engram --version 2>&1)"
        $installed = $true
      }
    } catch {}

    if (-not $installed) {
      # Fallback: install via Go if available
      if (Get-Command go -ErrorAction SilentlyContinue) {
        Info "  winget failed — trying Go install..."
        go install github.com/nicholasgasior/engram@latest
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path","User") + ";" +
                    "$env:USERPROFILE\go\bin"
        if (Get-Command engram -ErrorAction SilentlyContinue) {
          Success "  Engram installed via Go"
          $installed = $true
        }
      }
    }

    if (-not $installed) {
      Warn "  Could not install Engram automatically."
      Warn "  Install manually: winget install engram  OR  go install github.com/nicholasgasior/engram@latest"
      Warn "  Without Engram, Dexter loses memory between sessions."
    }
  } else {
    Success "  Engram already installed: $(engram --version 2>&1)"
  }
}

# ─── WhatsApp server setup ─────────────────────────────────────────────────────
function Setup-WhatsApp {
  $serverDir = Join-Path $PSScriptRoot "skills\communications\whatsapp\server"

  # Skip if the WhatsApp server is not bundled
  if (-not (Test-Path (Join-Path $serverDir "package.json"))) { return }
  if ($DryRun) { Info "[dry-run] Would set up WhatsApp server at $serverDir"; return }

  $answer = Read-Host "[Dexter] Set up WhatsApp notifications? (any regular WhatsApp number) [y/N]"
  if ($answer.ToLower() -ne "y") {
    Info "  Skipping WhatsApp setup. Run later from $serverDir"
    return
  }

  # Node.js is guaranteed by Install-Dependencies (Step 5) — no need to re-check here
  if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Warn "  Node.js not found even after dependency install — skipping WhatsApp setup."
    return
  }

  # Install npm dependencies
  Info "  Installing WhatsApp server dependencies..."
  Push-Location $serverDir
  npm install --silent
  Pop-Location
  Success "  Dependencies installed."

  # Pairing method
  $pairingMethod = Read-Host "[Dexter] Pairing method: (1) QR code  (2) Phone number [1]"
  $useQR = $pairingMethod -ne "2"

  # Save phone number to notifications config
  $phone = Read-Host "[Dexter] Your phone number for notifications (e.g. +5491112345678)"
  $configFile = Join-Path $env:USERPROFILE ".dexter\notifications.json"
  if ($phone -and (Test-Path $configFile)) {
    $cfg = Get-Content $configFile | ConvertFrom-Json
    $cfg.channel = "whatsapp"
    if (-not $cfg.whatsapp) { $cfg | Add-Member -NotePropertyName whatsapp -NotePropertyValue @{} }
    $cfg.whatsapp.api_url = "http://localhost:3000"
    $cfg.whatsapp.phone = $phone
    $cfg | ConvertTo-Json -Depth 5 | Set-Content $configFile
    Success "  Notifications config updated → channel: whatsapp, phone: $phone"
  }

  # Register as a Windows Task Scheduler task so the server runs at login
  # and stays alive without needing an open terminal.
  Info "  Registering WhatsApp server as a background Task Scheduler task..."
  $nodePath = (Get-Command node).Source
  $serverJs = Join-Path $serverDir "server.js"
  $nodeArgs  = if ($useQR) { "`"$serverJs`" --qr" } else { "`"$serverJs`"" }
  $action   = New-ScheduledTaskAction -Execute $nodePath -Argument $nodeArgs -WorkingDirectory $serverDir
  $trigger  = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit ([TimeSpan]::Zero)
  Register-ScheduledTask -TaskName "Dexter WhatsApp Server" -Action $action `
    -Trigger $trigger -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName "Dexter WhatsApp Server"
  Success "  Task registered and started. Runs automatically at every login."
  Info "  Manage: Task Scheduler → 'Dexter WhatsApp Server'"
  Info "  Logs:   $env:USERPROFILE\.dexter\whatsapp-server.log"
  if ($useQR) {
    Info "  First run: open Task Scheduler → run 'Dexter WhatsApp Server' → scan the QR in the terminal."
  }
}

# ─── WSL2 bridge ───────────────────────────────────────────────────────────────
function Setup-WSL2Bridge {
  if (-not (Detect-WSL2)) { return }

  Info "WSL2 detected — setting up bridge..."
  if ($DryRun) { Info "[dry-run] Would configure WSL2 bridge"; return }

  try {
    # Check if Dexter is installed in WSL2 and create a Windows → WSL2 shortcut
    $wslCheck = wsl bash -c "test -f ~/proyectos/Dexter/install.sh && echo 'found'" 2>&1
    if ($wslCheck -eq "found") {
      Success "Dexter found in WSL2 — bridge available"
      Info "  Use WSL2 for Linux-only skills: nmap, arp-scan, etc."
    } else {
      Warn "Dexter not found in WSL2. For Linux skills, install Dexter inside WSL2 too:"
      Info "  wsl bash -c 'cd ~/proyectos/Dexter && bash install.sh'"
    }
  } catch {
    Warn "Could not probe WSL2 — skipping bridge setup"
  }
}

# ─── Main ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ██████╗ ███████╗██╗  ██╗████████╗███████╗██████╗" -ForegroundColor Cyan
Write-Host "  ██╔══██╗██╔════╝╚██╗██╔╝╚══██╔══╝██╔════╝██╔══██╗" -ForegroundColor Cyan
Write-Host "  ██║  ██║█████╗   ╚███╔╝    ██║   █████╗  ██████╔╝" -ForegroundColor Cyan
Write-Host "  ██║  ██║██╔══╝   ██╔██╗    ██║   ██╔══╝  ██╔══██╗" -ForegroundColor Cyan
Write-Host "  ██████╔╝███████╗██╔╝ ██╗   ██║   ███████╗██║  ██║" -ForegroundColor Cyan
Write-Host "  ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝" -ForegroundColor Cyan
Write-Host "  v$DexterVersion — AI Ecosystem Configurator" -ForegroundColor Gray
Write-Host ""

$detectedAgent = Detect-Agent
if (-not $detectedAgent) {
  Warn "Could not auto-detect agent."
  $detectedAgent = Read-Host "[Dexter] Enter agent name (claude-code/opencode/codex/cursor/gemini/vscode)"
}

Info "Target agent: $detectedAgent"
if ($DryRun) { Warn "DRY RUN MODE — no files will be modified" }

$paths = Get-AgentPaths -AgentName $detectedAgent

Write-Host "`nStep 1: Backup" -ForegroundColor Blue
Backup-Files -Paths $paths

Write-Host "`nStep 2: System Prompt" -ForegroundColor Blue
Inject-SystemPrompt -Paths $paths

Write-Host "`nStep 3: Skills" -ForegroundColor Blue
Copy-Skills -SkillsDir $paths.SkillsDir

Write-Host "`nStep 4: MCPs" -ForegroundColor Blue
Configure-MCPs -Paths $paths -AgentName $detectedAgent

Write-Host "`nStep 5: Dependencies (Node.js + Engram)" -ForegroundColor Blue
Install-Dependencies

Write-Host "`nStep 6: WhatsApp Server" -ForegroundColor Blue
Setup-WhatsApp

Write-Host "`nStep 7: WSL2 Bridge" -ForegroundColor Blue
Setup-WSL2Bridge

Write-Host ""
Success "Dexter v$DexterVersion installed successfully!"
Info "  Agent  : $detectedAgent"
Info "  Backup : $BackupDir"
Info "  Config : $($paths.PromptFile)"
Write-Host ""
Info "Restart your agent to activate Dexter."
Info "Run .\uninstall.ps1 to revert all changes."
