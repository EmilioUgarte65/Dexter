package assets_test

import (
	"testing"

	"github.com/gentleman-programming/dexter/internal/assets"
)

func TestRead_DEXTER_returnsNonEmpty(t *testing.T) {
	b, err := assets.Read("DEXTER.md")
	if err != nil {
		t.Fatalf("Read(DEXTER.md) returned error: %v", err)
	}
	if len(b) == 0 {
		t.Fatal("Read(DEXTER.md) returned empty bytes")
	}
}

func TestRead_nonexistent_returnsError(t *testing.T) {
	_, err := assets.Read("nonexistent")
	if err == nil {
		t.Fatal("Read(nonexistent) expected error, got nil")
	}
}

func TestReadDEXTER(t *testing.T) {
	b, err := assets.ReadDEXTER()
	if err != nil {
		t.Fatalf("ReadDEXTER() error: %v", err)
	}
	if len(b) == 0 {
		t.Fatal("ReadDEXTER() returned empty bytes")
	}
}

func TestReadSOUL(t *testing.T) {
	b, err := assets.ReadSOUL()
	if err != nil {
		t.Fatalf("ReadSOUL() error: %v", err)
	}
	if len(b) == 0 {
		t.Fatal("ReadSOUL() returned empty bytes")
	}
}

func TestReadSkillsFS_returnsValidFS(t *testing.T) {
	subFS, err := assets.ReadSkillsFS()
	if err != nil {
		t.Fatalf("ReadSkillsFS() error: %v", err)
	}
	if subFS == nil {
		t.Fatal("ReadSkillsFS() returned nil FS")
	}
}

func TestReadMCPFS_returnsValidFS(t *testing.T) {
	subFS, err := assets.ReadMCPFS()
	if err != nil {
		t.Fatalf("ReadMCPFS() error: %v", err)
	}
	_ = subFS
}

func TestReadHooksJSON(t *testing.T) {
	b, err := assets.ReadHooksJSON()
	if err != nil {
		t.Fatalf("ReadHooksJSON() error: %v", err)
	}
	if len(b) == 0 {
		t.Fatal("ReadHooksJSON() returned empty bytes")
	}
}

func TestReadBlocklist(t *testing.T) {
	b, err := assets.ReadBlocklist()
	if err != nil {
		t.Fatalf("ReadBlocklist() error: %v", err)
	}
	if len(b) == 0 {
		t.Fatal("ReadBlocklist() returned empty bytes")
	}
}

func TestReadAgentOverlay_claudeCode(t *testing.T) {
	b, err := assets.ReadAgentOverlay("claude-code")
	if err != nil {
		t.Fatalf("ReadAgentOverlay(claude-code) error: %v", err)
	}
	if len(b) == 0 {
		t.Fatal("ReadAgentOverlay(claude-code) returned empty bytes")
	}
}

func TestReadAgentOverlay_unknownAgent_returnsError(t *testing.T) {
	_, err := assets.ReadAgentOverlay("does-not-exist")
	if err == nil {
		t.Fatal("ReadAgentOverlay(does-not-exist) expected error, got nil")
	}
}
