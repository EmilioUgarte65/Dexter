.PHONY: test test-installer test-scripts

# Run the full test suite
test: test-installer test-scripts

# bats-core — installer tests
# Install: brew install bats-core  |  apt-get install bats  |  npm install -g bats
test-installer:
	@if command -v bats >/dev/null 2>&1; then \
		bats tests/installer/install.bats; \
	else \
		echo ""; \
		echo "  bats-core not found — skipping installer tests."; \
		echo "  Install: brew install bats-core | apt-get install bats | npm install -g bats"; \
		echo ""; \
	fi

# pytest — Python script tests
# Install: pip install pytest  (Python 3.8+)
test-scripts:
	python3 -m pytest tests/scripts/ -v
