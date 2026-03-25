package installer

import "fmt"

// DeepMerge recursively merges src into dst.
// Rules:
//   - If both values are maps: recurse
//   - If both values are slices: append unique elements from src to dst
//   - If types differ: return error
//   - Otherwise: src wins (scalar overwrite)
func DeepMerge(dst, src map[string]any) (map[string]any, error) {
	result := make(map[string]any, len(dst))
	for k, v := range dst {
		result[k] = v
	}
	for k, srcVal := range src {
		dstVal, exists := result[k]
		if !exists {
			result[k] = srcVal
			continue
		}
		merged, err := mergeValues(k, dstVal, srcVal)
		if err != nil {
			return nil, err
		}
		result[k] = merged
	}
	return result, nil
}

// mergeValues merges two values at a given key according to deep-merge rules.
func mergeValues(key string, dst, src any) (any, error) {
	switch dstTyped := dst.(type) {
	case map[string]any:
		srcMap, ok := src.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("type conflict at key %q: dst is object, src is %T", key, src)
		}
		return DeepMerge(dstTyped, srcMap)
	case []any:
		srcSlice, ok := src.([]any)
		if !ok {
			return nil, fmt.Errorf("type conflict at key %q: dst is array, src is %T", key, src)
		}
		return appendUnique(dstTyped, srcSlice), nil
	default:
		// Check src is not a map or slice when dst is scalar — allow scalar overwrite
		switch src.(type) {
		case map[string]any:
			return nil, fmt.Errorf("type conflict at key %q: dst is %T, src is object", key, dst)
		case []any:
			return nil, fmt.Errorf("type conflict at key %q: dst is %T, src is array", key, dst)
		}
		// src scalar wins
		return src, nil
	}
}

// appendUnique appends elements from src to dst, skipping duplicates.
// Comparison is done via fmt.Sprintf for simplicity (handles primitives).
func appendUnique(dst, src []any) []any {
	seen := make(map[string]struct{}, len(dst))
	for _, v := range dst {
		seen[fmt.Sprintf("%v", v)] = struct{}{}
	}
	result := make([]any, len(dst))
	copy(result, dst)
	for _, v := range src {
		key := fmt.Sprintf("%v", v)
		if _, exists := seen[key]; !exists {
			result = append(result, v)
			seen[key] = struct{}{}
		}
	}
	return result
}
