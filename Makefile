PY := uv run --frozen python
STUBS := pins perf framing content trajectory correctness size similarity effort paper pitch blog

.PHONY: help lint test all env fetch c-subjects subjects $(STUBS)

help:
	@echo "lint   cargo fmt/clippy and ruff"
	@echo "test   cargo test, bins build and pytest"
	@echo "all    every measurement and kit"
	@echo "stubs: $(STUBS)"

env:
	$(PY) -m cfbench.env

fetch:
	$(PY) -m cfbench.cleanflate_src fetch
	$(PY) -m cfbench.cleanflate_src check

c-subjects:
	$(PY) -m cfbench.cbuild

subjects:
	cargo build --release --workspace --bins

lint:
	cargo fmt --all -- --check
	cargo clippy --workspace --all-targets -- -D warnings
	uv run --frozen ruff check cfbench tests
	uv run --frozen ruff format --check cfbench tests

test:
	cargo test --workspace
	cargo build --workspace --bins
	uv run --frozen pytest -q

$(STUBS):
	@echo "not implemented yet"; exit 2

all: env $(STUBS)
