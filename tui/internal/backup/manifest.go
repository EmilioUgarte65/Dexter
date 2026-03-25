package backup

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// ManifestEntry records the mapping between a backed-up file and its original location.
type ManifestEntry struct {
	OriginalPath string `json:"originalPath"`
	BackupPath   string `json:"backupPath"`
	AgentID      string `json:"agentID"`
}

// Manifest describes a point-in-time backup snapshot.
type Manifest struct {
	CreatedAt     time.Time       `json:"createdAt"`
	DexterVersion string          `json:"dexterVersion"`
	Entries       []ManifestEntry `json:"entries"`
}

// WriteManifest serialises m to <dir>/manifest.json.
func WriteManifest(dir string, m Manifest) error {
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "manifest.json"), data, 0o644)
}

// ReadManifest reads and deserialises the manifest from <dir>/manifest.json.
func ReadManifest(dir string) (Manifest, error) {
	data, err := os.ReadFile(filepath.Join(dir, "manifest.json"))
	if err != nil {
		return Manifest{}, err
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return Manifest{}, err
	}
	return m, nil
}
