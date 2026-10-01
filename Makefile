PY := uv run --frozen python
STUBS :=

.PHONY: kits kits-check content help lint test all env fetch c-subjects subjects pins workloads tools size perf perf-native subjects-native subjects-rounds trajectory effort conformance malformed bombs fuzz-build fuzz fuzz-report fuzz-smoke correctness paper paper-data pitch paper-check checksums framing content-features figures perf-report smoke-bench smoke-similarity similarity-ngram similarity-jplag similarity-fragments similarity-summary similarity smoke blog

help:
	@echo "help                  this list"
	@echo "lint                  cargo fmt/clippy and ruff"
	@echo "test                  cargo test, bins build and pytest"
	@echo "all                   every measurement, then every kit (human-run parts take hours)"
	@echo "env                   capture the machine environment"
	@echo "fetch                 fetch pinned sources and corpora"
	@echo "c-subjects            build the pinned C libraries (zlib, zlib-nohw, zlib-ng)"
	@echo "subjects              build every subject binary"
	@echo "pins                  record build provenance in subjects.lock.json"
	@echo "workloads             generate and verify the compressed workloads"
	@echo "tools                 install the pinned analysis tools"
	@echo "size                  binary size, bloat, unsafe, deps, LOC and complexity"
	@echo "perf                  full performance runs (human, quiet machine) and perf reports"
	@echo "perf-native           performance runs of the native-CPU variant"
	@echo "subjects-native       build the native-CPU subjects"
	@echo "subjects-rounds       build the three cleanflate round subjects"
	@echo "trajectory            benchmark each cleanflate round and derive the trajectory"
	@echo "effort                effort, cost and provenance tables"
	@echo "conformance           conformance of every subject over the shared corpus"
	@echo "malformed             malformed-input behaviour matrix"
	@echo "fuzz-build            build and test the fuzz targets"
	@echo "fuzz                  differential fuzzing for the full budget (human), coverage and triage"
	@echo "fuzz-report           derive fuzz tables from raw data"
	@echo "fuzz-smoke            short fuzz run into the smoke tree"
	@echo "bombs                 decompression-bomb sweep"
	@echo "correctness           conformance, malformed, fuzz and bombs"
	@echo "paper                 render results/PAPER_KIT.md"
	@echo "paper-data            run the machine-specific T1 measurements here, then make paper"
	@echo "pitch                 render results/PITCH_KIT"
	@echo "blog                  render RESULTS.md and BLOG_NOTES.md"
	@echo "kits                  paper, pitch and blog (re-derive and render only)"
	@echo "kits-check            regenerate the kits in a clean clone and compare byte for byte"
	@echo "paper-check           clean-clone check of the paper kit alone"
	@echo "checksums             checksum microbenchmarks"
	@echo "framing               framing overhead runs and hypothesis verdict"
	@echo "content               content analysis: features, correlation, findings"
	@echo "content-features      infgen features of every workload"
	@echo "figures               re-derive and render every figure"
	@echo "perf-report           derive the performance tables"
	@echo "smoke-bench           quick performance smoke run"
	@echo "smoke-similarity      similarity smoke run"
	@echo "smoke                 all smoke runs"
	@echo "similarity-ngram      token n-gram similarity"
	@echo "similarity-jplag      JPlag similarity"
	@echo "similarity-fragments  top fragment pairs for review"
	@echo "similarity-summary    similarity result statement"
	@echo "similarity            every similarity measurement"

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

bombs: subjects
	$(PY) -m cfbench.bombs run

malformed: subjects
	$(PY) -m cfbench.malformed run

correctness: conformance malformed fuzz bombs

paper:
	$(PY) -m cfbench.kits.paper

paper-data: env pins perf trajectory size conformance
	$(MAKE) paper

pitch:
	$(PY) -m cfbench.kits.pitch rederive
	$(MAKE) figures
	$(PY) -m cfbench.kits.pitch render

kits: paper pitch blog

kits-check:
	$(PY) -m cfbench.clean_clone kits --compare results/PAPER_KIT.md results/PITCH_KIT results/RESULTS.md results/BLOG_NOTES.md

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

figures:
	$(PY) -m cfbench.perf_charts
	$(PY) -m cfbench.trajectory derive
	$(PY) -m cfbench.framing derive
	$(PY) -m cfbench.similarity.summary
	$(PY) -m cfbench.more_charts

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
	$(PY) -m cfbench.loc
	$(PY) -m cfbench.complexity rust
	$(PY) -m cfbench.complexity c
	$(PY) -m cfbench.complexity derive

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

blog:
	$(PY) -m cfbench.kits.pitch rederive
	$(PY) -m cfbench.kits.results_md
	$(PY) -m cfbench.kits.blog

all: env pins perf perf-native framing content trajectory correctness size similarity effort paper pitch blog
