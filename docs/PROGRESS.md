# cleanflate-bench build progress
Branch: build/2026-10-01
Started: 2026-10-01T04:25:03.345Z

## Tasks
- [x] P0-01 Repository scaffold, config loader and Makefile skeleton
- [x] P0-02 Machine detection, environment capture and raw-data I/O
- [x] P0-03 Pinned cleanflate clone, corpora and pristine check
- [x] P0-04 Pinned C subject builds (zlib, zlib-nohw, zlib-ng)
- [x] P0-05 Rust timing harness core
- [x] P0-06 Rust subject binaries cf, zrs, mox
- [x] P0-07 zlib-API subject binaries zlib, zlib-nohw, zsys
- [x] P0-08 zlib-ng native-API subject binary
- [x] P0-09 Hardware-CRC determination, unsafe status and subjects.lock.json
- [x] P0-10 Workload generation and manifest
- [x] P0-11 Perf orchestrator and smoke bench
- [x] P0-12 Similarity tokenizer and smoke similarity run
- [x] P0-13 Phase 0 hand-off
- [x] P1-01 Statistics core
- [x] P1-02 Provenance-tracked tables and per-cell perf table
- [x] P1-03 Ratios, per-corpus aggregates and tiny-input table
- [x] P1-04 Run-to-run agreement check
- [x] P1-05 target-cpu=native Rust variant
- [x] P1-06 Chart helpers and throughput figure
- [x] P1-07 Phase 1 hand-off
- [x] P2-01 Pinned third-party tools
- [x] P2-02 Minimal stdin→stdout decompressors
- [x] P2-03 Binary-size measurement and cargo bloat
- [x] P2-04 Unsafe surface
- [x] P2-05 Dependencies and audit
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

### P0-02 — b495a66
Tests: test_machine x3, test_env x3, test_rawio x4. API: env.capture_environment(cmd,rd,system), capture_end(env,cmd), rawio.write_raw/list_raw/load_raw/latest_session(category,machine,kind,profile), rawio.bench_git(). Interpretation: on_ac null on desktop; cleanflate fields read from rounds.json primary_round when present; env payload {kind:'env',capture}. Committed data/raw/env/M-B run. Makefile: env target real.

### P0-03 — a2f4a7f
Tests: test_cleanflate_src x5 (throwaway repos). API: cleanflate_src.clone_path/rounds/primary_sha/git(path,*args)/ensure_clone/verify_tags/pristine_check/ensure_corpora/corpus_files(corpus)->[(name,path,sha,bytes)]. Cloned via ssh OK; silesia 12 files, canterbury 11. config/rounds.json created. make fetch real.

### P0-04 — f5df6e8
Tests: test_download x3, test_cbuild x4. Pins recorded in config/subjects.toml (zlib 1.3.2, zng 2.3.3 hashes pinned at task time). Libs: build/c/zlib/lib/libcfbz_default.a, build/c/zlib-nohw/lib/libcfbz_nohw.a, build/c/zng/lib/libz-ng.a; headers in include/. build-info.json has recipe, cflags, compiler, cmake_options (zng). x86_64: zlib-nohw control_identical_to_default true. API: download.fetch/extract, cbuild.build(id,force), cbuild.IDS.

### P0-05 — 2b50945
Tests: harness tests/timing.rs x3, alloc.rs x2, cli.rs x8. Subject API in harness::subject (Caps, OutputLimit, StreamOutcome, DecodeError, ERR_OUTPUT_FULL="output_full", ERR_UNSUPPORTED). Subjects must return kind "output_full" when oneshot buffer is too small. cli::run_main::<S>() / cli::run::<S>(args,out). c_zalloc/c_zfree are `unsafe extern "C" fn(*mut c_void,u32,u32)`. Caller output limit via unwind marker. Decode oneshot reports consumed=input.len, trailing=0. Heap pass includes oneshot out buffer. bench cell input/expected are file paths. Compress output JSON {ok,error,output_bytes}. Deps: serde, serde_json, sha2.

### P0-06 — c643c31
Tests: test_rust_subjects.py 13 cases (session fixture runs cargo build). Binaries cfb-cf/zrs/mox in target/{debug,release}. cf: max_output=u64::MAX unless given, default TrailingData::Reject (trailing -> error TrailingData), oneshot = single Decompressor call into caller buffer. zrs: z_stream via libz-rs-sys, windowBits -15/15/31, Caller limit. mox: raw/zlib only, adler32 via mz_adler32_oxide, no crc32, trailing_bytes reported. Rust subjects have no compress. Error kinds: cf ErrorKind names, zrs Z_* names, mox Debug names; oneshot buffer too small = "output_full". make subjects = cargo build --release --workspace --bins.

### P0-07 — cc14d2c
Tests: test_c_subjects.py (info versions, decode fixture, compress roundtrip L1/6/9 all framings, gzip header os255/mtime0, only zlib compresses, heap counted). New tests/cli_util.py (run/decode/build_debug/FIX/PLAIN/MODES) shared by subject tests. crates/zlibapi: generic Api<V: Variant> Subject; binaries cfb-zlib (compress), cfb-zlib-nohw, cfb-zsys (dylib -lz). Interpretation: build.rs uses rustc-link-arg-bins=-l<lib> (link-lib=static mis-orders and fails to link). Makefile lint/test/subjects depend on c-subjects. Trailing gzip members not looped; trailing_bytes reported.

### P0-08 — f0dc473
Tests: subj-zng inline unit zng_stream_layout_matches_header (build.rs C probe: sizeof+offsets, ZNG_STREAM_LAYOUT env); test_c_subjects now covers zng (version 2.3.3, decode, checksums for all C subjects). cfb-zng uses zng_* native API, Caller limit, no compress. Linked via rustc-link-arg-bins=-lz-ng.

### P0-09 — e084936
Tests: test_pins x8, test_unsafe_scan x3, test_sources x2. API: pins.hw_crc/merge_lock/rust_profile/mnemonics/collect/main, unsafe_scan.scan_crate/count_text (totals keys unsafe_blocks, unsafe_fns, unsafe_impls, unsafe_traits, target_feature; forbid_unsafe_code, deny_unsafe_code), sources.source_root/extra_roots/package_dirs. M-B data run committed (data/raw/pins/M-B, subjects.lock.json): zlib/zlib-nohw/zsys hw_crc compiled_in false; zng true w/ runtime dispatch (crc32_pclmulqdq, vpclmulqdq); zrs true; cf 0 unsafe + forbid; mox 0 unsafe; zrs 674 blocks. Dispatch pattern excludes chorba. M-A entry still to be recorded by a human (make pins).

### P0-10 — 61ebabd
Tests: test_workloads x7 (fake compressor, tmp DATA). API: workloads.list_workloads(cfg)->[Workload(id,corpus,file,level,framing,orig_path,path,orig_len,len)], generate(cfg,compressor,write_manifest), verify(cfg), load_manifest(). Layout data/workloads/<corpus>/<file>/{orig,l<level>.<framing>}, tiny at data/workloads/tiny/<corpus>-<file>-<prefix>/. 288 streams generated (207+81), manifest committed (zlib 1.3.2). Manifest verify checks only the active profile's list. Generation takes ~95s.

### P0-11 — 1dea1f0
Tests: test_perf x10, test_subjects x3, fixtures/fake_subject.py (flags --framings, --fail). API: subjects.SUBJECTS/SubjectSpec/binary_path(id,build)/command(id,build) (CFB_SUBJECT_CMD override); perf.build_cells/shuffled/check_preconditions/run(cfg,ids,variant,session,profile,strict,build,runner). Raw perf payload {kind,variant,build,seed,subjects,cells[{subject,workload,corpus,level,framing,mode,in_chunk,out_chunk,order_index,result|status:unsupported}],preconditions,environment_end}; one file per run with shared session. Native binaries assumed at target/native/release, cf rounds at build/rounds/rN/cfb-cf. Smoke bench ran: 2 files x 270 cells, all ok (mox gzip unsupported); smoke not committed. make perf/smoke-bench real.

### P0-12 — b5d6e86
Tests: test_similarity_tokens x7, test_similarity_ngram x5. API: tokens.tokenize(path,language)->[Token(kind,text,line).norm], tokens.comments(path)->[(line,text)], tokens.language_for; ngram.shingles/jaccard/containment/file_shingles/compare(files_a,files_b,n). Config [similarity] ngram_min=5 ngram_max=10. docs/methods/similarity.md has vocabulary table. Smoke cf~mox n=5 Jaccard 0.214 (smoke only). make smoke-similarity, make smoke real. Deps added: tree-sitter 0.26.0, tree-sitter-rust 0.24.2, tree-sitter-c 0.24.2.

### P0-13 — b81f6cb
Push: git push -u origin HEAD succeeded (build/2026-10-01).
Checklist (verbatim):
1. On M-A (Apple M4): `make fetch c-subjects subjects pins` succeeds, and `subjects.lock.json` gains an `M-A` entry in which zlib shows `compiled_in: true` (`crc32x` present) and zlib-nohw shows `compiled_in: false`.
2. On M-A: `make env workloads smoke` completes; commit the env and pins raw files.
3. `python -m cfbench.workloads verify` passes on M-A, which proves the workloads are byte-identical across machines.
Manual check: NOT VERIFIED (human)

### P1-01 — 8cfd4b9
Tests: test_stats x8. API: stats.median/best/bootstrap_ci(xs,level,resamples,rng:random.Random)/mib_per_s(bytes,ns)/ns_per_byte/cell_stats(samples,out_bytes,cfg,rng)->CellStats/like_for_like_key(cell dict: machine,session,workload,level,framing,mode)/ratio_vs_baseline/ratios_vs_baseline(cells,baseline='zlib') (cells need subject, median_mib_s + key fields). Bootstrap via numpy default_rng(rng.getrandbits(64)). Missing baseline => None.

### P1-02 — 4569819
Tests: test_provenance x4, test_perf_report x5 (fixtures tests/fixtures/raw/perf/M-T: old/new sessions + native). API: provenance.write_table(name,columns,rows(list of dict),script=,raw_files=,pending=)/read_table(name)->(rows of str dicts, sidecar)/fmt/to_float/table_path; perf_report.load_sessions()->{(machine,variant):[doc+path]}, pooled_cells(docs), derive_cells(cfg), CELL_COLUMNS. perf_cells.csv columns per task. Rng random.Random(seed) iterated over sorted cells. No-data case writes header + pending 'no full perf runs; run make perf on M-A and M-B'.

### P1-03 — 4045d55
Tests: test_perf_report +6 (aggregate, no cross-mode ratios, incomplete flag, tiny ratio, all-tables-from-fixtures, pending for all). API: perf_report.compute_rows(cfg)->(rows with hidden _median_ns/_best_ns/_ci_lo_ns/_ci_hi_ns, raw_files), add_ratios, aggregates(rows), tiny_rows(rows), derive_all(cfg) (writes perf_cells, perf_aggregates, perf_tiny), CELL/AGG/TINY_COLUMNS. perf_cells gained ratio_vs_zlib. Aggregate ratio None unless zlib covers same file set. results/perf_*.csv committed as pending. make perf-report added; make perf chains it.

### P1-04 — 58b7119
Tests: test_agreement x5. API: agreement.compare_session(docs,tol)->(flagged rows, summary), derive(cfg), FLAG_COLUMNS, SUMMARY_COLUMNS. Tables perf_agreement(.csv) and perf_agreement_summary. Verdict pass/flagged/insufficient runs from aggregates only; first two runs compared; make perf-report also runs agreement. Pending sidecars committed.

### P1-05 — 494140e
Tests: test_perf native labels + native run, test_subjects native path/labels. API: perf.session_labels(cfg,variant); subjects.native_label/split_label; native run payload variant native, build native, subjects cf@native/zrs@native/mox@native + zlib baseline. make subjects-native (target/native), make perf-native (depends subjects+subjects-native, then perf-report). pins records cf@native etc. (target_cpu native, rustflags) - M-B pins rerun committed. Native smoke ran ok.

### P1-06 — 713892d
Tests: test_charts x7. API: parity.PARITY_NOTE/with_context(machine,variant); charts.save_figure(fig,name,*,parity_note,size,out_dir)->[svg,png] (2x base_dpi PNG, deterministic svg/png metadata), charts.new_figure(size)/size_inches; perf_charts.throughput_data/draw_throughput/throughput_figure(machine,variant). New [charts] config keys: paper_height_in, default_width_in, default_height_in, footnote_pt, font_family. Figure: perf_throughput_<machine>[_native]. Pending (no figure) without perf data. PNG visually inspected.

### P1-07 — f6ced68
Push: git push -u origin HEAD succeeded.
Checklist (verbatim):
1. On M-A (on AC, lid open, low-power off, quiet), then on M-B (governor `performance`): run `make perf` (two full runs, roughly 2-3 h each) and `make perf-native`, then commit `data/raw/perf/<machine>/`.
2. `make perf-report`: check that `results/perf_agreement_summary.csv` shows `pass` for both machines, or review the flagged cells.
3. Look at `results/figures/perf_throughput_M-A.png` and `perf_throughput_M-B.png`.
Manual check: NOT VERIFIED (human)

### P2-01 — 2a9f39d
Tests: test_tools x6. API: tools.ensure(name, runner)->ToolStatus(name,version,path,ok,error), tools.binary_path(binary), tools.all_names(). config/tools.toml has version, binary, version_args per tool (cargo-bloat uses ['bloat','--version']). make tools installed all three: cargo-bloat 0.12.1, cargo-geiger 0.13.0, cargo-audit 0.22.2 at third_party/tools/bin (build took ~8 min). No tool gaps on M-B.

### P2-02 — 5780a8b
Tests: test_minimal_programs x9. Bins min-cf/min-zrs/min-mox (crates/min-*, no harness dep, 64 KiB streaming, exit 1 + single 'error: ...' stderr line on failure). C sources minimal/c/min_zlib.c and min_zng.c written (zlib API / zng_ API) - untested until P2-03 builds them. cf uses Options::default so trailing data is rejected; zrs/mox stop at stream end.

### P2-03 — 25e16ea
Tests: test_size x7 (+1 test_cbuild). API: size.rust_build_cmd/bloat_cmd/c_link_flags/zlib_sources/parse_bloat/rows_from_payload/measure_binary/derive_binary; target_dir(opt,stripped). Config [size] opt_levels ['3','s'], bloat_top 30. Fixed zng source dir naming (cbuild.SOURCE_DIR_NAMES: zng->zlib-ng, matching sources.source_root); build-info untouched. M-B data run committed: sizes (opt3 bytes) zlib 43136, zng 158040, mox 361120, cf 393888, zrs 406184; opt s: zlib 34944, zng 100696, mox 340640, cf 373408, zrs 381608; zsys excluded row. No tool gaps. make size = tools + cfbench.size binary (P2-04/P2-05 to chain).

### P2-04 — de55b3d
Tests: test_unsafe_scan +5 (dependency rows incl. build/dev exclusion, geiger failure gap, geiger parse, C note, table+lock status from latest raw). API: unsafe_scan.scan_subject(subject, metadata), geiger_counts(subject, runner), collect(), derive_table(), status_from_latest_raw(subject), main; UNSAFE_COLUMNS. cargo-geiger runs on crates/min-<x>/Cargo.toml (virtual workspace manifest unsupported). Raw: data/raw/size/any (kind unsafe), results/unsafe.csv. Results: cf 0 unsafe, forbid true, 0 deps; mox 0 unsafe + adler2 0; zrs 674 unsafe blocks. pins lock unsafe_status reads latest raw. make size runs unsafe_scan after binary.

### P2-05 — 300d180
Tests: test_deps x5. API: deps.parse_tree/parse_audit/filter_advisories/run_audit(runner)/collect(metadata,runner,audit_runner)/derive_table/main. Data run committed (size/any kind deps; results/deps.csv): cf 0/0 deps; mox 1/1 (adler2); libz-rs-sys 1/1 (zlib-rs); zlib-rs 0/0; no advisories in any dependency set. cargo-audit worked (no tool gap). make size = binary + unsafe_scan + deps.
