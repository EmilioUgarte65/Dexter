BINARY := dexter
CMD    := ./cmd/dexter
ASSETS_SRC := ..
ASSETS_DST := internal/assets/data

.PHONY: build run clean sync-assets

# sync-assets copies source files from the repo root into the embed data dir.
# Copies (not symlinks) are used because go:embed does not follow symlinks,
# and symlinks are not supported on Windows.
sync-assets:
	@echo "==> Syncing assets to $(ASSETS_DST)/"
	@mkdir -p $(ASSETS_DST)/mcp $(ASSETS_DST)/skills $(ASSETS_DST)/agents/claude-code \
		$(ASSETS_DST)/agents/opencode $(ASSETS_DST)/agents/codex \
		$(ASSETS_DST)/agents/cursor $(ASSETS_DST)/agents/gemini \
		$(ASSETS_DST)/agents/vscode
	@cp $(ASSETS_SRC)/DEXTER.md        $(ASSETS_DST)/
	@cp $(ASSETS_SRC)/SOUL.md          $(ASSETS_DST)/
	@cp $(ASSETS_SRC)/CAPABILITIES.md  $(ASSETS_DST)/
	@cp $(ASSETS_SRC)/blocklist.json   $(ASSETS_DST)/
	@cp $(ASSETS_SRC)/hooks/hooks.json $(ASSETS_DST)/
	@cp $(ASSETS_SRC)/gga/AGENTS.md   $(ASSETS_DST)/
	@cp -r $(ASSETS_SRC)/skills/.     $(ASSETS_DST)/skills/
	@cp -r $(ASSETS_SRC)/mcp/.        $(ASSETS_DST)/mcp/
	@cp $(ASSETS_SRC)/agents/claude-code/overlay.json $(ASSETS_DST)/agents/claude-code/
	@cp $(ASSETS_SRC)/agents/claude-code/paths.sh     $(ASSETS_DST)/agents/claude-code/
	@cp $(ASSETS_SRC)/agents/opencode/sdd-overlay-multi.json  $(ASSETS_DST)/agents/opencode/
	@cp $(ASSETS_SRC)/agents/opencode/sdd-overlay-single.json $(ASSETS_DST)/agents/opencode/
	@cp $(ASSETS_SRC)/agents/opencode/paths.sh  $(ASSETS_DST)/agents/opencode/
	@cp $(ASSETS_SRC)/agents/codex/paths.sh     $(ASSETS_DST)/agents/codex/
	@cp $(ASSETS_SRC)/agents/cursor/paths.sh    $(ASSETS_DST)/agents/cursor/
	@cp $(ASSETS_SRC)/agents/gemini/paths.sh    $(ASSETS_DST)/agents/gemini/
	@cp $(ASSETS_SRC)/agents/vscode/paths.sh    $(ASSETS_DST)/agents/vscode/
	@echo "==> Assets synced"

build: sync-assets
	go build -ldflags "-X main.version=$$(git describe --tags --always --dirty 2>/dev/null || echo dev)" -o $(BINARY) $(CMD)

run:
	go run -ldflags "-X main.version=dev" $(CMD)

clean:
	rm -f $(BINARY)
