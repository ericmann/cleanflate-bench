PY := uv run --frozen python
STUBS := framing content trajectory correctness similarity effort paper pitch blog

.PHONY: help lint test all env fetch c-subjects subjects pins workloads tools size perf perf-native subjects-native perf-report smoke-bench smoke-similarity similarity-ngram similarity-jplag smoke $(STUBS)

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
	$(MAKE) perf-report

perf-native: subjects subjects-native
	$(PY) -m cfbench.perf run --variant native
	$(MAKE) perf-report

subjects-native: c-subjects
	RUSTFLAGS="-C target-cpu=native" cargo build --release -p subj-cf -p subj-zrs -p subj-mox --target-dir target/native

perf-report:
	$(PY) -m cfbench.perf_report
	$(PY) -m cfbench.agreement
	$(PY) -m cfbench.perf_charts

smoke-bench: subjects
	CFB_PROFILE=quick $(PY) -m cfbench.perf run

smoke-similarity:
	$(PY) -m cfbench.similarity.smoke

smoke: smoke-bench smoke-similarity

tools:
	$(PY) -m cfbench.tools ensure

size: tools
	$(PY) -m cfbench.size binary
	$(PY) -m cfbench.unsafe_scan
	$(PY) -m cfbench.deps

similarity-ngram:
	$(PY) -m cfbench.similarity.run ngram
	$(PY) -m cfbench.similarity.run identifiers
	$(PY) -m cfbench.similarity.run comments

similarity-jplag:
	$(PY) -m cfbench.similarity.jplag

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

all: env pins perf size $(STUBS)
