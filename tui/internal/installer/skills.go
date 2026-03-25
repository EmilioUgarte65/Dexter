package installer

import (
	"bytes"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
)

// CopySkills copies the embedded skills/ tree to skillsDir on the real filesystem.
//
// Behaviour:
//   - Existing files are skipped only if their content matches exactly; otherwise overwritten.
//   - Parent directories are created as needed.
//   - dryRun=true reports what would change without writing.
//
// fsys should be the sub-filesystem rooted at the embedded skills/ directory
// (i.e. from assets.ReadSkillsFS()).
func CopySkills(skillsDir string, fsys fs.FS, dryRun bool) error {
	var errs []error

	err := fs.WalkDir(fsys, ".", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}

		target := filepath.Join(skillsDir, filepath.FromSlash(path))
		data, err := fs.ReadFile(fsys, path)
		if err != nil {
			return fmt.Errorf("copy_skills: read embedded %q: %w", path, err)
		}

		if dryRun {
			existing, readErr := os.ReadFile(target)
			if os.IsNotExist(readErr) {
				fmt.Printf("[dry-run] copy_skills: would create %s\n", target)
			} else if readErr != nil {
				fmt.Printf("[dry-run] copy_skills: would overwrite %s (unreadable: %v)\n", target, readErr)
			} else if !bytes.Equal(existing, data) {
				fmt.Printf("[dry-run] copy_skills: would overwrite %s (content differs)\n", target)
			} else {
				fmt.Printf("[dry-run] copy_skills: skip %s (identical)\n", target)
			}
			return nil
		}

		// Skip if content matches.
		if existing, readErr := os.ReadFile(target); readErr == nil {
			if bytes.Equal(existing, data) {
				return nil
			}
		}

		if mkErr := os.MkdirAll(filepath.Dir(target), 0o755); mkErr != nil {
			errs = append(errs, fmt.Errorf("copy_skills: mkdir %q: %w", filepath.Dir(target), mkErr))
			return nil
		}

		if writeErr := os.WriteFile(target, data, 0o644); writeErr != nil {
			errs = append(errs, fmt.Errorf("copy_skills: write %q: %w", target, writeErr))
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("copy_skills: walk: %w", err)
	}
	return joinErrors(errs)
}
