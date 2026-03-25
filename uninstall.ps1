# Dexter Uninstaller — Windows (PowerShell 5+)
# Usage: .\uninstall.ps1 [-BackupDir <path>] [-DryRun]
[CmdletBinding()]
param(
  [string]$BackupDir = "",
  [switch]$DryRun
)

$BackupBase = "$env:USERPROFILE\.dexter-backup"

function Info    { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Cyan }
function Success { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Green }
function Warn    { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Yellow }
function Err     { param([string]$msg) Write-Host "[Dexter] $msg" -ForegroundColor Red }

# ─── Find latest backup ────────────────────────────────────────────────────────
function Find-Backup {
  if ($BackupDir) { return $BackupDir }

  if (-not (Test-Path $BackupBase)) {
    Err "No backup directory found at $BackupBase"
    Write-Host "Manually remove Dexter blocks from your agent config files." -ForegroundColor Yellow
    exit 1
  }

  $latest = Get-ChildItem $BackupBase -Directory | Sort-Object Name -Descending | Select-Object -First 1
  if (-not $latest) {
    Err "No backups found in $BackupBase"
    exit 1
  }
  return $latest.FullName
}

# ─── Strip markers from a file ────────────────────────────────────────────────
function Strip-Markers {
  param([string]$File)
  if (-not (Test-Path $File)) { return }
  $content = Get-Content $File -Raw
  if ($content -notmatch "<!-- dexter:core -->") { return }

  Info "Stripping Dexter markers from $File ..."
  if ($DryRun) { Info "[dry-run] Would strip markers from $File"; return }

  $stripped = $content -replace "<!-- dexter:core -->[\s\S]*?<!-- /dexter:core -->", ""
  Set-Content $File $stripped.TrimEnd()
  Success "Stripped markers from $File"
}

# ─── Restore from backup ──────────────────────────────────────────────────────
function Restore-FromBackup {
  param([string]$BkDir)
  $manifest = "$BkDir\manifest.json"

  if (-not (Test-Path $manifest)) {
    Warn "No manifest in $BkDir — will only strip markers"
    return
  }

  Info "Restoring from backup: $BkDir"
  if (Get-Command node -ErrorAction SilentlyContinue) {
    node -e "
      const fs=require('fs'),path=require('path');
      const home=process.env.USERPROFILE;
      const manifest=JSON.parse(fs.readFileSync('$manifest','utf8'));
      manifest.files.forEach(e=>{
        const orig=e.path.replace('~',home);
        const bk=path.join('$BkDir',orig.replace(home,''));
        if(fs.existsSync(bk)){
          fs.mkdirSync(path.dirname(orig),{recursive:true});
          fs.copyFileSync(bk,orig);
          console.log('  Restored: '+e.path);
        } else {
          console.log('  Warning: not found in backup: '+e.path);
        }
      });
    "
  } else {
    Warn "Node.js not found — manually restore from $BkDir"
  }
}

# ─── Remove Dexter skills ─────────────────────────────────────────────────────
function Remove-DexterSkills {
  $appData = $env:APPDATA
  $home    = $env:USERPROFILE

  $skillsDirs = @(
    "$appData\Claude\skills",
    "$appData\OpenCode\skills",
    "$home\.codex\skills",
    "$appData\Cursor\skills",
    "$home\.gemini\skills"
  )

  $dexterBundles = @(
    "_shared", "communications", "email", "productivity", "social",
    "research", "media", "knowledge", "dev", "cloud", "infrastructure",
    "domotics", "security", "ai-local", "self-extend", "openclaw-adapter"
  )

  foreach ($skillsDir in $skillsDirs) {
    if (-not (Test-Path $skillsDir)) { continue }

    foreach ($bundle in $dexterBundles) {
      $bundlePath = "$skillsDir\$bundle"
      if (Test-Path $bundlePath) {
        if ($DryRun) { Info "[dry-run] Would remove $bundlePath" }
        else {
          Remove-Item $bundlePath -Recurse -Force
          Success "  Removed bundle: $bundle from $skillsDir"
        }
      }
    }

    # Remove CAPABILITIES.md
    $caps = "$skillsDir\CAPABILITIES.md"
    if (Test-Path $caps) {
      if (-not $DryRun) { Remove-Item $caps -Force }
      Success "  Removed: CAPABILITIES.md"
    }
  }
}

# ─── Main ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Dexter Uninstaller" -ForegroundColor Red
Write-Host ""

$resolvedBackup = Find-Backup
Info "Using backup: $resolvedBackup"

if ($DryRun) { Warn "DRY RUN MODE — no files will be modified" }

Write-Host "`nStep 1: Restoring original files..." -ForegroundColor Blue
Restore-FromBackup -BkDir $resolvedBackup

Write-Host "`nStep 2: Stripping Dexter markers..." -ForegroundColor Blue
$stripTargets = @(
  "$env:USERPROFILE\.cursorrules",
  "$env:USERPROFILE\.gemini\GEMINI.md",
  "$env:USERPROFILE\.codex\instructions.md",
  "$env:USERPROFILE\.github\copilot-instructions.md"
)
foreach ($f in $stripTargets) { Strip-Markers -File $f }

Write-Host "`nStep 3: Removing Dexter skills..." -ForegroundColor Blue
Remove-DexterSkills

Write-Host ""
Success "Dexter uninstalled. Your original config has been restored."
Info "Restart your agent to complete the removal."
