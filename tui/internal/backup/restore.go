package backup

import (
	"errors"
	"fmt"
)

// Restore copies every backed-up file in m back to its original location.
// Parent directories are created as needed. The backup directory is NOT removed.
//
// Restore is partial-failure tolerant: if one or more files cannot be restored
// the operation continues with the remaining entries. All errors are accumulated
// and returned together via errors.Join so the caller can inspect each failure.
// The returned error includes a summary of how many files succeeded and how many
// failed.
func Restore(m Manifest) error {
	var errs []error
	ok, failed := 0, 0

	for _, entry := range m.Entries {
		if err := copyFile(entry.BackupPath, entry.OriginalPath); err != nil {
			errs = append(errs, fmt.Errorf("restore %q → %q: %w", entry.BackupPath, entry.OriginalPath, err))
			failed++
		} else {
			ok++
		}
	}

	if len(errs) == 0 {
		return nil
	}

	summary := fmt.Errorf("restore completed with errors: %d ok, %d failed", ok, failed)
	return errors.Join(append([]error{summary}, errs...)...)
}
