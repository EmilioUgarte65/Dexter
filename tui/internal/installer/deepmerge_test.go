package installer

import (
	"testing"
)

func TestDeepMerge_ObjectMerge(t *testing.T) {
	tests := []struct {
		name     string
		dst      map[string]any
		src      map[string]any
		wantKeys map[string]any // spot-check expected keys; nil means check not needed
		wantErr  bool
	}{
		{
			name: "src wins on scalar conflict",
			dst:  map[string]any{"a": "old", "b": "keep"},
			src:  map[string]any{"a": "new"},
			wantKeys: map[string]any{
				"a": "new",
				"b": "keep",
			},
		},
		{
			name: "nested object merge",
			dst:  map[string]any{"mcpServers": map[string]any{"existing": map[string]any{}}},
			src:  map[string]any{"mcpServers": map[string]any{"dexter": map[string]any{}}},
			// Both keys should be present after merge.
			wantKeys: nil,
		},
		{
			name: "missing key from src added",
			dst:  map[string]any{"a": 1},
			src:  map[string]any{"b": 2},
			wantKeys: map[string]any{
				"a": 1,
				"b": 2,
			},
		},
		{
			name:    "type conflict object vs array",
			dst:     map[string]any{"servers": map[string]any{}},
			src:     map[string]any{"servers": []any{}},
			wantErr: true,
		},
		{
			name:    "type conflict array vs object",
			dst:     map[string]any{"servers": []any{}},
			src:     map[string]any{"servers": map[string]any{}},
			wantErr: true,
		},
		{
			name: "empty src returns dst copy",
			dst:  map[string]any{"a": "x"},
			src:  map[string]any{},
			wantKeys: map[string]any{
				"a": "x",
			},
		},
		{
			name: "empty dst returns src copy",
			dst:  map[string]any{},
			src:  map[string]any{"a": "x"},
			wantKeys: map[string]any{
				"a": "x",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := DeepMerge(tt.dst, tt.src)
			if (err != nil) != tt.wantErr {
				t.Fatalf("DeepMerge() error = %v, wantErr %v", err, tt.wantErr)
			}
			if tt.wantErr {
				return
			}
			for k, want := range tt.wantKeys {
				got, ok := result[k]
				if !ok {
					t.Errorf("missing key %q in result", k)
					continue
				}
				if got != want {
					t.Errorf("key %q: got %v (%T), want %v (%T)", k, got, got, want, want)
				}
			}
		})
	}
}

func TestDeepMerge_NestedObjectMerge(t *testing.T) {
	dst := map[string]any{
		"mcpServers": map[string]any{
			"existing": map[string]any{"command": "old"},
		},
	}
	src := map[string]any{
		"mcpServers": map[string]any{
			"dexter": map[string]any{"command": "engram"},
		},
	}

	result, err := DeepMerge(dst, src)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	servers, ok := result["mcpServers"].(map[string]any)
	if !ok {
		t.Fatal("mcpServers is not a map")
	}
	if _, exists := servers["existing"]; !exists {
		t.Error("existing key missing from merged mcpServers")
	}
	if _, exists := servers["dexter"]; !exists {
		t.Error("dexter key missing from merged mcpServers")
	}
}

func TestDeepMerge_ArrayAppend(t *testing.T) {
	tests := []struct {
		name     string
		dst      map[string]any
		src      map[string]any
		key      string
		wantLen  int
		wantVals []any
	}{
		{
			name:     "basic append",
			dst:      map[string]any{"tools": []any{"a"}},
			src:      map[string]any{"tools": []any{"b"}},
			key:      "tools",
			wantLen:  2,
			wantVals: []any{"a", "b"},
		},
		{
			name:     "skip duplicates",
			dst:      map[string]any{"tools": []any{"a", "b"}},
			src:      map[string]any{"tools": []any{"b", "c"}},
			key:      "tools",
			wantLen:  3,
			wantVals: []any{"a", "b", "c"},
		},
		{
			name:     "src only (empty dst slice)",
			dst:      map[string]any{"tools": []any{}},
			src:      map[string]any{"tools": []any{"x"}},
			key:      "tools",
			wantLen:  1,
			wantVals: []any{"x"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := DeepMerge(tt.dst, tt.src)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			gotSlice, ok := result[tt.key].([]any)
			if !ok {
				t.Fatalf("key %q is not a slice", tt.key)
			}
			if len(gotSlice) != tt.wantLen {
				t.Errorf("len = %d, want %d; got %v", len(gotSlice), tt.wantLen, gotSlice)
			}
			// Check each expected value present.
			for _, want := range tt.wantVals {
				found := false
				for _, v := range gotSlice {
					if v == want {
						found = true
						break
					}
				}
				if !found {
					t.Errorf("value %v not found in slice %v", want, gotSlice)
				}
			}
		})
	}
}

func TestDeepMerge_TypeConflict(t *testing.T) {
	tests := []struct {
		name string
		dst  map[string]any
		src  map[string]any
	}{
		{
			name: "dst object src array",
			dst:  map[string]any{"servers": map[string]any{"a": 1}},
			src:  map[string]any{"servers": []any{"b"}},
		},
		{
			name: "dst array src object",
			dst:  map[string]any{"tools": []any{"a"}},
			src:  map[string]any{"tools": map[string]any{"b": 1}},
		},
		{
			name: "dst scalar src object",
			dst:  map[string]any{"name": "alice"},
			src:  map[string]any{"name": map[string]any{"first": "alice"}},
		},
		{
			name: "dst scalar src array",
			dst:  map[string]any{"name": "alice"},
			src:  map[string]any{"name": []any{"alice"}},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := DeepMerge(tt.dst, tt.src)
			if err == nil {
				t.Error("expected error, got nil")
			}
		})
	}
}
