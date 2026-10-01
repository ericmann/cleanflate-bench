# cleanflate-bench build progress
Branch: build/2026-10-01
Started: 2026-10-01T04:25:03.345Z

## Tasks
- [x] P0-01 Repository scaffold, config loader and Makefile skeleton
- [ ] P0-02 Machine detection, environment capture and raw-data I/O
- [ ] P0-03 Pinned cleanflate clone, corpora and pristine check
- [ ] P0-04 Pinned C subject builds (zlib, zlib-nohw, zlib-ng)
- [ ] P0-05 Rust timing harness core
- [ ] P0-06 Rust subject binaries cf, zrs, mox
- [ ] P0-07 zlib-API subject binaries zlib, zlib-nohw, zsys
- [ ] P0-08 zlib-ng native-API subject binary
- [ ] P0-09 Hardware-CRC determination, unsafe status and subjects.lock.json
- [ ] P0-10 Workload generation and manifest
- [ ] P0-11 Perf orchestrator and smoke bench
- [ ] P0-12 Similarity tokenizer and smoke similarity run
- [ ] P0-13 Phase 0 hand-off
- [ ] P1-01 Statistics core
- [ ] P1-02 Provenance-tracked tables and per-cell perf table
- [ ] P1-03 Ratios, per-corpus aggregates and tiny-input table
- [ ] P1-04 Run-to-run agreement check
- [ ] P1-05 target-cpu=native Rust variant
- [ ] P1-06 Chart helpers and throughput figure
- [ ] P1-07 Phase 1 hand-off
- [ ] P2-01 Pinned third-party tools
- [ ] P2-02 Minimal stdin→stdout decompressors
- [ ] P2-03 Binary-size measurement and cargo bloat
- [ ] P2-04 Unsafe surface
- [ ] P2-05 Dependencies and audit
- [ ] P2-06 Phase 2 hand-off
- [ ] P3-01 Decompression-path source manifest
- [ ] P3-02 Token n-gram similarity for all pairs
- [ ] P3-03 Identifier and comment overlap
- [ ] P3-04 JPlag for same-language pairs
- [ ] P3-05 Top-20 fragment pairs with persistent verdicts
- [ ] P3-06 Positioning against controls, statement and figure
- [ ] P3-07 Structural comparison write-up
- [ ] P3-08 Phase 3 hand-off
- [ ] P4-01 Round builds of cf
- [ ] P4-02 Trajectory run, table and figure
- [ ] P4-03 Effort from git history, tool log and Foundry state
- [ ] P4-04 Token usage export and cost
- [ ] P4-05 zlib-rs status-quo context
- [ ] P4-06 Effort tables, gaps and trajectory join
- [ ] P4-07 Phase 4 hand-off
- [ ] P5-01 Conformance runner
- [ ] P5-02 Claims engine with evidence links
- [ ] P5-03 Paper table and figure
- [ ] P5-04 PAPER_KIT renderer and make paper
- [ ] P5-05 Clean-clone regeneration check
- [ ] P5-06 Phase 5 hand-off
- [ ] P6-01 Checksum microbenchmarks
- [ ] P6-02 Framing overhead, the hardware-CRC hypothesis and figure
- [ ] P6-03 Phase 6 hand-off
- [ ] P7-01 infgen build and parser
- [ ] P7-02 Content features for every workload
- [ ] P7-03 Correlation, H1/H2 verdicts, scatter plots and findings
- [ ] P7-04 Phase 7 hand-off
- [ ] P8-01 Malformed-input behaviour matrix
- [ ] P8-02 Differential fuzz harnesses
- [ ] P8-03 Fuzz orchestration, statistics and corpus archive
- [ ] P8-04 Fuzz coverage and divergence triage
- [ ] P8-05 Decompression-bomb robustness sweep
- [ ] P8-06 Phase 8 hand-off
- [ ] P9-01 Decompression-path LOC with tokei
- [ ] P9-02 Rust complexity distributions
- [ ] P9-03 C complexity and the complexity table
- [ ] P9-04 Phase 9 hand-off
- [ ] P10-01 Remaining figures
- [ ] P10-02 PITCH_KIT and talking points
- [ ] P10-03 RESULTS.md, part 1 (performance, framing, content, trajectory)
- [ ] P10-04 RESULTS.md, part 2 (correctness, size/safety, similarity, effort, threats)
- [ ] P10-05 BLOG_NOTES.md
- [ ] P10-06 make all and the clean-clone check for every kit
- [ ] P10-07 Phase 10 hand-off

## Log
(one entry per task, appended by implement)

### P0-01 — 90271ed
Tests: test_config.py x4, harness framing unit test. Cargo.lock committed; hatchling backend. Stub targets exit 2. config/bench.toml has initial [run][machines][perf][charts] and quick profile.
