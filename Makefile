PY := uv run --frozen python
STUBS := pitch blog

.PHONY: content help lint test all env fetch c-subjects subjects pins workloads tools size perf perf-native subjects-native subjects-rounds trajectory effort conformance malformed fuzz-build fuzz fuzz-report fuzz-smoke correctness paper paper-check checksums framing content-features perf-report smoke-bench smoke-similarity similarity-ngram similarity-jplag similarity-fragments similarity-summary similarity smoke $(STUBS)

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

subjects-rounds:
	for n in 1 2 3; do \
	  cargo build --release -p subj-cf --no-default-features --features round$$n --target-dir target/round$$n || exit 1; \
	done

trajectory: subjects subjects-rounds
	$(PY) -m cfbench.trajectory run
	$(PY) -m cfbench.trajectory derive

effort:
	$(PY) -m cfbench.effort.history
	$(PY) -m cfbench.effort.usage
	$(PY) -m cfbench.effort.context
	$(PY) -m cfbench.effort.derive

conformance: subjects workloads
	$(PY) -m cfbench.conformance run

fuzz-build: c-subjects
	cargo fmt --manifest-path fuzz/Cargo.toml -- --check
	cd fuzz && cargo +nightly test
	cd fuzz && cargo +nightly fuzz build

fuzz: fuzz-build
	$(PY) -m cfbench.fuzzing run
	$(PY) -m cfbench.fuzzing report

fuzz-report:
	$(PY) -m cfbench.fuzzing report

fuzz-smoke: fuzz-build
	CFB_PROFILE=quick $(PY) -m cfbench.fuzzing run
	CFB_PROFILE=quick $(PY) -m cfbench.fuzzing report

malformed: subjects
	$(PY) -m cfbench.malformed run

correctness: conformance malformed

paper:
	$(PY) -m cfbench.kits.paper

paper-check:
	$(PY) -m cfbench.clean_clone paper --compare results/PAPER_KIT.md results/figures/paper_throughput_unsafe.svg

checksums: subjects
	$(PY) -m cfbench.checksums run

framing: checksums
	$(PY) -m cfbench.framing run
	$(PY) -m cfbench.framing derive

content: content-features
	$(PY) -m cfbench.content.correlate

content-features: tools workloads
	$(PY) -m cfbench.content.features run

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

similarity-fragments:
	$(PY) -m cfbench.similarity.fragments

similarity-summary:
	$(PY) -m cfbench.similarity.summary

similarity: similarity-ngram similarity-jplag similarity-fragments
	$(PY) -m cfbench.similarity.summary

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

all: env pins perf size similarity trajectory effort correctness paper framing content-features $(STUBS)
