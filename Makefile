PY := uv run --frozen python
STUBS := framing content trajectory correctness size similarity effort paper pitch blog

.PHONY: help lint test all env fetch c-subjects subjects pins workloads perf smoke-bench smoke-similarity smoke $(STUBS)

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

subjects: c-subjects
	cargo build --release --workspace --bins

pins: c-subjects subjects
	$(PY) -m cfbench.pins

workloads: fetch subjects
	$(PY) -m cfbench.workloads generate
	$(PY) -m cfbench.workloads verify

perf: subjects
	$(PY) -m cfbench.perf run

smoke-bench: subjects
	CFB_PROFILE=quick $(PY) -m cfbench.perf run

smoke-similarity:
	$(PY) -m cfbench.similarity.smoke

smoke: smoke-bench smoke-similarity

lint: c-subjects
	cargo fmt --all -- --check
	cargo clippy --workspace --all-targets -- -D warnings
	uv run --frozen ruff check cfbench tests
	uv run --frozen ruff format --check cfbench tests

test: c-subjects
	cargo test --workspace
	cargo build --workspace --bins
	uv run --frozen pytest -q

$(STUBS):
	@echo "not implemented yet"; exit 2

all: env pins perf $(STUBS)
