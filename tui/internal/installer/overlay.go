package installer

import (
	"encoding/json"
	"fmt"
)

// OverlayMergeResult holds the output of an ApplyOverlay call.
type OverlayMergeResult struct {
	// Merged is the resulting JSON (pretty-printed, 2-space indent).
	Merged []byte
	// Changed reports whether the merged result differs from baseJSON.
	Changed bool
}

// ApplyOverlay deep-merges overlayJSON onto baseJSON.
//
// Merge rules (in priority order):
//   - mcpServers: shallow merge (overlay wins per-key)
//   - hooks: shallow merge (overlay wins per-key)
//   - permissions.allow / permissions.deny: union + dedup
//   - outputStyle: overlay wins
//   - All other keys: recursive deep merge (DeepMerge)
//   - Type conflicts: return error with key + type info
//
// If baseJSON is nil or empty, the result equals overlayJSON.
func ApplyOverlay(baseJSON, overlayJSON []byte) (OverlayMergeResult, error) {
	base := make(map[string]any)
	if len(baseJSON) > 0 {
		if err := json.Unmarshal(baseJSON, &base); err != nil {
			return OverlayMergeResult{}, fmt.Errorf("overlay: invalid base JSON: %w", err)
		}
	}

	overlay := make(map[string]any)
	if len(overlayJSON) > 0 {
		if err := json.Unmarshal(overlayJSON, &overlay); err != nil {
			return OverlayMergeResult{}, fmt.Errorf("overlay: invalid overlay JSON: %w", err)
		}
	}

	merged, err := applyOverlayMaps(base, overlay)
	if err != nil {
		return OverlayMergeResult{}, err
	}

	out, err := json.MarshalIndent(merged, "", "  ")
	if err != nil {
		return OverlayMergeResult{}, fmt.Errorf("overlay: failed to marshal result: %w", err)
	}

	// Detect change: compare canonical marshalling of both
	baseSerialized, _ := json.Marshal(base)
	mergedSerialized, _ := json.Marshal(merged)
	changed := string(baseSerialized) != string(mergedSerialized)

	return OverlayMergeResult{Merged: out, Changed: changed}, nil
}

// applyOverlayMaps merges overlay into base with specialised rules for known keys.
func applyOverlayMaps(base, overlay map[string]any) (map[string]any, error) {
	// Start with a shallow copy of base.
	result := make(map[string]any, len(base))
	for k, v := range base {
		result[k] = v
	}

	for key, srcVal := range overlay {
		switch key {
		case "outputStyle":
			// Scalar: overlay always wins.
			result[key] = srcVal

		case "hooks":
			// Shallow merge: overlay wins per-key.
			result[key] = shallowMergeObjects(base[key], srcVal, key)

		case "mcpServers":
			// Shallow merge: overlay wins per-key.
			result[key] = shallowMergeObjects(base[key], srcVal, key)

		case "permissions":
			// Special: merge allow/deny as union sets.
			merged, err := mergePermissions(base[key], srcVal)
			if err != nil {
				return nil, err
			}
			result[key] = merged

		default:
			dstVal, exists := result[key]
			if !exists {
				result[key] = srcVal
				continue
			}
			merged, err := mergeValues(key, dstVal, srcVal)
			if err != nil {
				return nil, err
			}
			result[key] = merged
		}
	}
	return result, nil
}

// shallowMergeObjects performs a shallow merge of src into dst (both expected to be maps).
// If either side is not a map, src wins.
func shallowMergeObjects(dst, src any, _ string) any {
	dstMap, dstOK := dst.(map[string]any)
	srcMap, srcOK := src.(map[string]any)
	if !dstOK || !srcOK {
		return src
	}
	result := make(map[string]any, len(dstMap)+len(srcMap))
	for k, v := range dstMap {
		result[k] = v
	}
	for k, v := range srcMap {
		result[k] = v
	}
	return result
}

// mergePermissions merges two permissions objects, unioning allow/deny slices.
func mergePermissions(dstAny, srcAny any) (map[string]any, error) {
	result := make(map[string]any)

	dstMap, _ := dstAny.(map[string]any)
	srcMap, _ := srcAny.(map[string]any)

	// Copy dst first.
	for k, v := range dstMap {
		result[k] = v
	}

	for _, listKey := range []string{"allow", "deny"} {
		dstList, _ := dstMap[listKey].([]any)
		srcList, _ := srcMap[listKey].([]any)
		if len(srcList) > 0 {
			result[listKey] = appendUnique(dstList, srcList)
		}
	}

	// Merge any other keys from src permissions.
	for k, v := range srcMap {
		if k == "allow" || k == "deny" {
			continue
		}
		result[k] = v
	}

	return result, nil
}
