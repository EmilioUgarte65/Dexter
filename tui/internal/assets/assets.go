package assets

import (
	"embed"
	"fmt"
	"io/fs"
)

//go:embed all:data
var FS embed.FS

// Read returns the contents of a file in the embedded data directory.
// path should be relative to data/, e.g. "DEXTER.md" or "skills/_shared/bundle-loader.md".
func Read(path string) ([]byte, error) {
	return FS.ReadFile("data/" + path)
}

// MustRead returns the contents of a file or panics if the file cannot be read.
func MustRead(path string) []byte {
	b, err := Read(path)
	if err != nil {
		panic(fmt.Sprintf("assets: failed to read %q: %v", path, err))
	}
	return b
}

// ReadDEXTER returns the contents of DEXTER.md.
func ReadDEXTER() ([]byte, error) {
	return Read("DEXTER.md")
}

// ReadSOUL returns the contents of SOUL.md.
func ReadSOUL() ([]byte, error) {
	return Read("SOUL.md")
}

// ReadCapabilities returns the contents of CAPABILITIES.md.
func ReadCapabilities() ([]byte, error) {
	return Read("CAPABILITIES.md")
}

// ReadSkillsFS returns a sub-filesystem rooted at the embedded skills/ directory.
func ReadSkillsFS() (fs.FS, error) {
	return fs.Sub(FS, "data/skills")
}

// ReadMCPFS returns a sub-filesystem rooted at the embedded mcp/ directory.
func ReadMCPFS() (fs.FS, error) {
	return fs.Sub(FS, "data/mcp")
}

// ReadAgentOverlay returns the overlay.json for the given agent name.
// agentName should match the directory name, e.g. "claude-code" or "opencode".
func ReadAgentOverlay(agentName string) ([]byte, error) {
	return Read("agents/" + agentName + "/overlay.json")
}

// ReadHooksJSON returns the contents of hooks/hooks.json.
func ReadHooksJSON() ([]byte, error) {
	return Read("hooks.json")
}

// ReadBlocklist returns the contents of blocklist.json.
func ReadBlocklist() ([]byte, error) {
	return Read("blocklist.json")
}
