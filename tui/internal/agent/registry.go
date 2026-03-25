package agent

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

// AgentID is a stable string identifier for a supported AI coding agent.
type AgentID string

const (
	AgentClaudeCode AgentID = "claude-code"
	AgentOpenCode   AgentID = "opencode"
	AgentCodex      AgentID = "codex"
	AgentCursor     AgentID = "cursor"
	AgentGemini     AgentID = "gemini"
	AgentVSCode     AgentID = "vscode"
)

// SystemPromptStrategy identifies how Dexter injects the system prompt file.
type SystemPromptStrategy string

const (
	StrategyMarkdownSections SystemPromptStrategy = "MarkdownSections"
	StrategyFileReplace      SystemPromptStrategy = "FileReplace"
	StrategyAppendToFile     SystemPromptStrategy = "AppendToFile"
)

// MCPStrategy identifies how Dexter writes MCP configuration for an agent.
type MCPStrategy string

const (
	MCPSeparateFiles MCPStrategy = "SeparateMCPFiles"
	MCPJSONMerge     MCPStrategy = "JSONMerge"
	MCPConfigFile    MCPStrategy = "MCPConfigFile"
	MCPTOMLFile      MCPStrategy = "TOMLFile"
)

// AgentConfig holds all path and strategy metadata for a single AI coding agent.
// Path functions accept homeDir so they can be exercised in tests with a fake home.
type AgentConfig struct {
	ID                   AgentID
	DisplayName          string
	ConfigDir            func(homeDir string) string // OS-aware config root
	SystemPromptFile     func(homeDir string) string
	SystemPromptStrategy SystemPromptStrategy
	SkillsDir            func(homeDir string) string
	SettingsFile         func(homeDir string) string
	MCPStrategy          MCPStrategy
	// OverlayFile is the path inside the assets FS (e.g. "agents/claude-code/overlay.json").
	// Empty when the agent has no overlay.
	OverlayFile string
	// DetectFn returns true when the agent is present on the current system.
	DetectFn func(homeDir string) bool
	// BackupFiles returns the list of files that should be snapshotted before install.
	BackupFiles func(homeDir string) []string
}

// Registry returns all 6 supported agents sorted by AgentID.
func Registry() []AgentConfig {
	return []AgentConfig{
		claudeCodeAgent(),
		codexAgent(),
		cursorAgent(),
		geminiAgent(),
		openCodeAgent(),
		vsCodeAgent(),
	}
}

// Detect runs every agent's DetectFn and returns only those present on the system.
func Detect(homeDir string) []DetectionResult {
	var results []DetectionResult
	for _, a := range Registry() {
		configDir := a.ConfigDir(homeDir)
		_, statErr := os.Stat(configDir)
		found := statErr == nil
		binary := ""
		if !found {
			// Also check PATH for the binary named after the agent ID.
			if p, err := exec.LookPath(string(a.ID)); err == nil {
				binary = p
				found = true
			}
		}
		results = append(results, DetectionResult{
			Agent:     a.ID,
			Found:     found,
			ConfigDir: configDir,
			Binary:    binary,
		})
	}
	return results
}

// ---------------------------------------------------------------------------
// Per-agent constructors
// ---------------------------------------------------------------------------

func claudeCodeAgent() AgentConfig {
	configDir := func(homeDir string) string {
		return filepath.Join(homeDir, ".claude")
	}
	return AgentConfig{
		ID:          AgentClaudeCode,
		DisplayName: "Claude Code",
		ConfigDir:   configDir,
		SystemPromptFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "CLAUDE.md")
		},
		SystemPromptStrategy: StrategyMarkdownSections,
		SkillsDir: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "skills")
		},
		SettingsFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "settings.json")
		},
		MCPStrategy: MCPSeparateFiles,
		OverlayFile: "agents/claude-code/overlay.json",
		DetectFn: func(homeDir string) bool {
			_, err := os.Stat(configDir(homeDir))
			if err == nil {
				return true
			}
			_, err = exec.LookPath("claude")
			return err == nil
		},
		BackupFiles: func(homeDir string) []string {
			base := configDir(homeDir)
			return []string{
				filepath.Join(base, "CLAUDE.md"),
				filepath.Join(base, "settings.json"),
			}
		},
	}
}

func openCodeAgent() AgentConfig {
	configDir := func(homeDir string) string {
		switch runtime.GOOS {
		case "windows":
			appData := os.Getenv("APPDATA")
			if appData == "" {
				appData = filepath.Join(homeDir, "AppData", "Roaming")
			}
			return filepath.Join(appData, "opencode")
		default: // linux, darwin
			return filepath.Join(homeDir, ".config", "opencode")
		}
	}
	return AgentConfig{
		ID:          AgentOpenCode,
		DisplayName: "OpenCode",
		ConfigDir:   configDir,
		SystemPromptFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "AGENTS.md")
		},
		SystemPromptStrategy: StrategyFileReplace,
		SkillsDir: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "skills")
		},
		SettingsFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "config.json")
		},
		MCPStrategy: MCPJSONMerge,
		OverlayFile: "",
		DetectFn: func(homeDir string) bool {
			_, err := os.Stat(configDir(homeDir))
			if err == nil {
				return true
			}
			_, err = exec.LookPath("opencode")
			return err == nil
		},
		BackupFiles: func(homeDir string) []string {
			base := configDir(homeDir)
			return []string{
				filepath.Join(base, "AGENTS.md"),
				filepath.Join(base, "config.json"),
			}
		},
	}
}

func codexAgent() AgentConfig {
	configDir := func(homeDir string) string {
		return filepath.Join(homeDir, ".codex")
	}
	return AgentConfig{
		ID:          AgentCodex,
		DisplayName: "Codex CLI",
		ConfigDir:   configDir,
		SystemPromptFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "instructions.md")
		},
		SystemPromptStrategy: StrategyAppendToFile,
		SkillsDir: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "skills")
		},
		SettingsFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "config.toml")
		},
		MCPStrategy: MCPTOMLFile,
		OverlayFile: "",
		DetectFn: func(homeDir string) bool {
			_, err := os.Stat(configDir(homeDir))
			if err == nil {
				return true
			}
			_, err = exec.LookPath("codex")
			return err == nil
		},
		BackupFiles: func(homeDir string) []string {
			base := configDir(homeDir)
			return []string{
				filepath.Join(base, "instructions.md"),
				filepath.Join(base, "config.toml"),
			}
		},
	}
}

func cursorAgent() AgentConfig {
	configDir := func(homeDir string) string {
		return filepath.Join(homeDir, ".cursor")
	}
	return AgentConfig{
		ID:          AgentCursor,
		DisplayName: "Cursor",
		ConfigDir:   configDir,
		SystemPromptFile: func(homeDir string) string {
			// Cursor uses a .cursorrules file at home root (not inside configDir).
			return filepath.Join(homeDir, ".cursorrules")
		},
		SystemPromptStrategy: StrategyAppendToFile,
		SkillsDir: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "skills")
		},
		SettingsFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "mcp.json")
		},
		MCPStrategy: MCPConfigFile,
		OverlayFile: "",
		DetectFn: func(homeDir string) bool {
			_, err := os.Stat(configDir(homeDir))
			if err == nil {
				return true
			}
			_, err = exec.LookPath("cursor")
			return err == nil
		},
		BackupFiles: func(homeDir string) []string {
			return []string{
				filepath.Join(homeDir, ".cursorrules"),
				filepath.Join(configDir(homeDir), "mcp.json"),
			}
		},
	}
}

func geminiAgent() AgentConfig {
	configDir := func(homeDir string) string {
		return filepath.Join(homeDir, ".gemini")
	}
	return AgentConfig{
		ID:          AgentGemini,
		DisplayName: "Gemini CLI",
		ConfigDir:   configDir,
		SystemPromptFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "GEMINI.md")
		},
		SystemPromptStrategy: StrategyAppendToFile,
		SkillsDir: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "skills")
		},
		SettingsFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "settings.json")
		},
		MCPStrategy: MCPJSONMerge,
		OverlayFile: "",
		DetectFn: func(homeDir string) bool {
			_, err := os.Stat(configDir(homeDir))
			if err == nil {
				return true
			}
			_, err = exec.LookPath("gemini")
			return err == nil
		},
		BackupFiles: func(homeDir string) []string {
			base := configDir(homeDir)
			return []string{
				filepath.Join(base, "GEMINI.md"),
				filepath.Join(base, "settings.json"),
			}
		},
	}
}

func vsCodeAgent() AgentConfig {
	configDir := func(homeDir string) string {
		switch runtime.GOOS {
		case "darwin":
			return filepath.Join(homeDir, "Library", "Application Support", "Code")
		case "windows":
			appData := os.Getenv("APPDATA")
			if appData == "" {
				appData = filepath.Join(homeDir, "AppData", "Roaming")
			}
			return filepath.Join(appData, "Code")
		default: // linux
			return filepath.Join(homeDir, ".config", "Code")
		}
	}
	// VS Code uses GitHub Copilot instructions stored at ~/.github/copilot-instructions.md.
	systemPromptFile := func(homeDir string) string {
		return filepath.Join(homeDir, ".github", "copilot-instructions.md")
	}
	return AgentConfig{
		ID:          AgentVSCode,
		DisplayName: "VS Code (Copilot)",
		ConfigDir:   configDir,
		SystemPromptFile:     systemPromptFile,
		SystemPromptStrategy: StrategyAppendToFile,
		SkillsDir: func(homeDir string) string {
			return filepath.Join(homeDir, ".vscode", "extensions", "dexter-skills")
		},
		SettingsFile: func(homeDir string) string {
			return filepath.Join(configDir(homeDir), "User", "settings.json")
		},
		MCPStrategy: MCPConfigFile,
		OverlayFile: "",
		DetectFn: func(homeDir string) bool {
			_, err := os.Stat(filepath.Join(configDir(homeDir), "User"))
			if err == nil {
				return true
			}
			_, err = exec.LookPath("code")
			return err == nil
		},
		BackupFiles: func(homeDir string) []string {
			return []string{
				systemPromptFile(homeDir),
				filepath.Join(configDir(homeDir), "User", "settings.json"),
			}
		},
	}
}
