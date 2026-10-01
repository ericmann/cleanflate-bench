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
- [x] P2-06 Phase 2 hand-off
- [x] P3-01 Decompression-path source manifest
- [x] P3-02 Token n-gram similarity for all pairs
- [x] P3-03 Identifier and comment overlap
- [x] P3-04 JPlag for same-language pairs
- [x] P3-05 Top-20 fragment pairs with persistent verdicts
- [x] P3-06 Positioning against controls, statement and figure
- [x] P3-07 Structural comparison write-up
- [x] P3-08 Phase 3 hand-off
- [x] P4-01 Round builds of cf
- [x] P4-02 Trajectory run, table and figure
- [x] P4-03 Effort from git history, tool log and Foundry state
- [x] P4-04 Token usage export and cost
- [x] P4-05 zlib-rs status-quo context
- [x] P4-06 Effort tables, gaps and trajectory join
- [x] P4-07 Phase 4 hand-off
- [x] P5-01 Conformance runner
- [x] P5-02 Claims engine with evidence links
- [x] P5-03 Paper table and figure
- [x] P5-04 PAPER_KIT renderer and make paper
- [x] P5-05 Clean-clone regeneration check
- [x] P5-06 Phase 5 hand-off
- [x] P6-01 Checksum microbenchmarks
- [x] P6-02 Framing overhead, the hardware-CRC hypothesis and figure
- [x] P6-03 Phase 6 hand-off
- [x] P7-01 infgen build and parser
- [x] P7-02 Content features for every workload
- [x] P7-03 Correlation, H1/H2 verdicts, scatter plots and findings
- [x] P7-04 Phase 7 hand-off
- [x] P8-01 Malformed-input behaviour matrix
- [x] P8-02 Differential fuzz harnesses
- [x] P8-03 Fuzz orchestration, statistics and corpus archive
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

### P2-06 — 0e6327c
Push: git push -u origin HEAD succeeded.
Checklist (verbatim):
1. On M-A: `make tools size`, then commit `data/raw/size/M-A/`.
2. Review `results/unsafe.csv` and `results/deps.csv` against a manual skim of the crates.
3. Note any tool gaps recorded in the raw files.
Manual check: NOT VERIFIED (human)

### P3-01 — bdaf520
Tests: test_decomp_paths x5. API: decomp_paths.files(subject, metadata)->sorted Paths, resolve(subject, roots, spec), spec(subject), StaleManifest, SUBJECTS. File counts: cf 17, zlib 13, zng 93, zrs 26, mox 5; none contain deflate. Interpretation: trailing '/**' globs expanded to '/**/*' (pathlib 3.12 quirk); zng arch files for all ISAs; zrs c_api.rs included whole, libz-rs-sys excluded; mox lib.rs excluded. docs/methods/decomp-paths.md documents the rule.

### P3-02 — 04ec5d4
Tests: test_similarity_pairs x5, tokens deep-nesting test. API: pairs.load_pairs(cfg)->[{left,right,role,cross_language}], file_token_lists(files), shingle_union(lists,n), compare_pair(left,right,cfg)->rows n=ngram_min..max {n,jaccard,containment,size_left,size_right}; run.ngram_payload/cmd_ngram, run.COMMANDS registry (extend per subcommand). Config [similarity].pairs. tokens._walk made iterative (recursion overflow bug). Data run: raw similarity/any 20261001T051802Z. n=5 Jaccard: zrs-mox 0.215 (negative), zrs-zng 0.056 (positive), cf-zrs 0.223, cf-mox 0.215, cf-zlib 0.035, cf-zng 0.035. Note the positive control (zrs-zng) scores LOWER than the negative control under this method (cross-language), a point for the P3-06 positioning write-up.

### P3-03 — a844869
Tests: test_similarity_identifiers x5, test_similarity_comments x3. API: identifiers.normalize/load_exclusions/parse_exclusions/collect(files,min_len,excluded)/compare; comments.words/comment_shingles(files,n)->(set,count)/compare; run.py identifiers + comments subcommands. Config [similarity] min_ident_len=6, comment_ngram=5. Token gained node field. config/rfc_identifiers.txt (rfc + '# language' sections) copied to results/similarity_identifier_exclusions.txt. Data: identifier Jaccard negative zrs-mox 0.044, positive zrs-zng 0.144, cf-zrs 0.053, cf-mox 0.075, cf-zlib 0.021, cf-zng 0.011; comment 5-gram Jaccard negative 0.0010, positive 0.0395, cf pairs <=0.0005. Raw: similarity/any 20261001T052006Z (identifiers), 20261001T052008Z (comments).

### P3-04 — 2f1710b
Tests: test_similarity_jplag x6 (fixtures/jplag: help_languages, comparison, runInformation, options). API: jplag.ensure_jar/ensure_java/ensure_jre/verify/parse_languages/parse_comparison/parse_result_archive/classify/all_pairs/run_pair/payload. Pinned jar sha 5f2c21e8..., JRE 25 pinned per platform (Linux-x86_64, Darwin-arm64) because PATH java is 21 and JPlag 6.3.0 needs 25. Use -M RUN. Rust+C support verified, no tool gap. Results (avg/max): zrs-mox 0.131/0.442 (negative control), cf-zrs 0.181/0.324 (longest match 594 tokens), cf-mox 0.180/0.290, zlib-zng 0.300/0.565 (context); cross-language pairs 'not applicable (cross-language)'. NOTE for review: cf-zrs has a 594-token longest match; P3-05 fragment review should look at it. config [similarity] context_pairs added. Raw similarity/any 20261001T052552Z.

### P3-05 — b782b35
Tests: test_similarity_fragments x9. API: fragments.find_fragments(left,right,min_len,top_k,max_occurrences)->(frags,skipped), fragment_id, parse_verdicts/load_verdicts/merge_verdicts, pair_rows, payload, markdown, derive(doc_path). Config [similarity] top_k=20, max_window_occurrences=50. Tables similarity_fragments_<left>_<right>.csv for all 6 pairs (controls included) + results/similarity_fragments/*.md. Verdict file empty (human). Interpretation: boilerplate windows (>50 occurrences) skipped (uncapped run took ~7 min); skipped counts recorded per pair. Longest fragments: zrs-mox 43, zrs-zng 54, cf-zrs 38, cf-mox 43, cf-zlib 24, cf-zng 15 tokens. cf-zrs top fragments are the Adler-32 loop (RFC-defined algorithm) and gzip/weak_slice. JPlag's 594-token cf-zrs match is structural (gzip.rs 561-719 vs inflate.rs 1057-1224, state-machine shape), not text. Raw similarity/any 20261001T053550Z.
Manual check: NOT VERIFIED (human): fill verdicts.

### P3-06 — e60322a
Tests: test_similarity_summary x7. API: summary.collect_scores/summarize/classify/position/failing_metrics/statement/draw/derive. Config [similarity] near_fraction=0.25. Outputs: results/similarity_summary.csv(+provenance), results/similarity_statement.md, results/figures/similarity_controls.svg/.png (PNG inspected). make similarity = ngram+identifiers+comments, jplag, fragments, summary; make similarity-summary derives only.
RESULT (honest): statement reads 'T1 claim NOT allowed': ident_jaccard cf-mox between (pos 0.31), ident_match_rate_left cf-zrs between (pos 0.32). N-gram metrics and jplag_avg cannot separate/position (positive control cross-language zrs-zng scores below negative zrs-mox; JPlag has no positive); cf-zrs/cf-mox n-gram Jaccard is 1.0-1.08x the negative control. Comment overlap below negative for all cf pairs. cf-zlib/cf-zng below negative everywhere. For P5+/review: the claim is NOT supported by the data; do not put a similarity-at-baseline claim in the paper kit.

### P3-07 — 1e06f7c
results/STRUCTURE_COMPARISON.md written: 6 sections (bit reader, Huffman tables, window, fast loop, state machine, observations), header with pinned versions, citations per subject per section (cf 22, zlib 21, zng 17, zrs 18, mox 14). Findings stated plainly: cf body states map 1:1 onto zlib modes (also RFC order); two-level root+subtable shared by cf/zlib/zng/zrs, mox differs; give-back-unread-bytes step common to cf/zlib/zng; zrs mirrors zlib naming/structure much more than cf. Cross-referenced with the similarity statement (T1 similarity claim NOT allowed).

### P3-08 — b83eb83
Push: git push -u origin HEAD succeeded.
Checklist (verbatim):
1. Fill in verdicts for the top-20 fragments of each test pair in `config/similarity_verdicts.toml`, then rerun `python -m cfbench.similarity.fragments`.
2. Review `results/STRUCTURE_COMPARISON.md` for accuracy.
3. Check `results/similarity_statement.md` and decide whether the claim wording is acceptable.
Manual check: NOT VERIFIED (human)
Note for the human: the generated statement currently reads 'T1 claim NOT allowed' (identifier metrics place cf-mox and cf-zrs between the controls; n-gram and JPlag metrics cannot be positioned). Rerunning the fragments command makes a new raw run; `python -m cfbench.similarity.fragments` derive step alone is `derive()` in that module.

### P4-01 — 64a9fca
Tests: test_subjects +2 (round paths, Cargo revs == rounds.json), test_rust_subjects round decode x3 (built on demand, never skipped). subj-cf features round1/round2/round3 (default round3) via renamed git deps cleanflate_r1..r3; Cargo accepted three revisions in one lock, no fallback workspace. Round binaries: target/round<N>/release/cfb-cf (make subjects-rounds); subjects.binary_path('cf-rN') or ('cf','roundN'); SUBJECTS gained cf-r1..r3 (kind round). impl_version 'cleanflate 0.1.0 round N @sha'. perf.build_cells etc unchanged (cf-rN not in perf.subjects).

### P4-02 — cf79778
Tests: test_trajectory x5. API: trajectory.trajectory_cfg/run/round_info/table_rows/derive/figure_series/draw/figure; perf.run(category,kind) and perf_report.compute_rows(cfg,category,kind) generalised. Config [trajectory] subjects/modes/levels/runs (+quick levels [6]). Raw category trajectory, kind trajectory, variant rounds; table results/trajectory.csv (pending committed); figure trajectory_<machine>. make trajectory = subjects + subjects-rounds + run + derive. Quick smoke ran fine (4 subjects x 30 cells). Full run is a human step.
Manual check: NOT VERIFIED (human): make trajectory on M-A and M-B.

### P4-03 — 69d3632
Tests: test_effort_history x5 (fixtures/effort: gitlog, tool-log, state-r1/r2, interventions). API: history.parse_git_log/round_windows/stage_wall_clock/milestone/parse_tool_log/tool_log_summary/categorize_denial/defect_source/defects_summary/parse_interventions/intervention_round/state_summary/collect(clone,cfg,git,rounds). Config [effort] idle_gap_hours=3, defect_keywords, denial_categories. docs/methods/effort.md. Raw effort/any 20261001T054826Z. Data: attributed wall-clock h r1 8.5/r2 7.3 (+8.0 idle)/r3 12.7; review rounds 4/3/2; denials 15/5/12; interventions 2/7/2; defects found 10/4/2 vs none 47/33/36. Models counted as tool calls per stage (opus-5-5 mostly; sonnet-5-5 for plan and summarize in r2-r3). Durations of interventions: documented gap. Note for P4-04/06: cleanflate commit messages carry stage tags; token/cost sources are separate.

### P4-04 — 045fd8c
Tests: test_effort_usage x7 (synthetic transcripts fixtures with sentinel text). API: usage.read_records/export_record/attribute/stage_from_agent/cost_of/summarize/collect/main(--allow-gaps); EXPORT_FIELDS/DERIVED_FIELDS. config/pricing.toml all UNSET (cost null, gaps list each model); [effort] transcripts_dir. history.state_summary reviews[] now has 'at'; history re-run -> newer raw 20261001T055110Z (older one still committed; latest wins). Usage raw: effort/any 20261001T055110Z-1.json (3291 msgs, 2518 dups dropped, no content/text keys, verified by grep). Output tokens by round/stage computed; costs null until prices supplied (human). Stage methods: agent type 2182, agent type after first review 919, main session 190 records.
Manual check: NOT VERIFIED (human): supply sourced prices in config/pricing.toml.

### P4-05 — 0c1a127
Tests: test_effort_context x5 (recorded responses, no network). API: context.last_page/count_via_last_page/releases/crate_versions/collect(fetch)/table_rows(payload,fetched_at)/derive/main; open_url is the single network call. Raw effort/any 20261001T055248Z; results/zlibrs_context.csv with scope_note row. Facts: zlib-rs first commit 2023-12-05, 1083 commits, 37 contributors incl. anonymous, first GitHub release v0.2.0 2024-06-12, first crate version 0.0.1 2024-02-23, latest 0.6.8 2026-09-15, no 1.0 published. GITHUB_TOKEN used if set, never stored. Note: a failed attempt of my own test sent a fake token to the live API once (401), no real token involved.

### P4-06 — 186924a
Tests: test_effort_derive x4. API: derive.build_tables(history, usage, trajectory)/gaps_markdown/derive; TABLES dict of columns. Tables: effort_stage_round, effort_totals (+idle_s, total row), effort_milestones, effort_review_rounds, effort_defects, effort_interventions, effort_denied, trajectory_with_effort (pending until trajectory.csv has rows); results/EFFORT_GAPS.md generated. Costs all null (prices unset) and listed as gaps. Wall-clock attributed s r1/r2/r3 = 30485/26218/45863 (+28931 idle in r2); output tokens 850772/168462/143298. make effort = history+usage+context+derive.

### P4-07 — 1f1af76
Push: git push -u origin HEAD succeeded.
Checklist (verbatim):
1. `make trajectory` on M-A and on M-B (quiet machine), then commit `data/raw/trajectory/`.
2. Fill in `config/pricing.toml` from the published price list (with `source` and `as_of`), then rerun `make effort`.
3. Confirm that `results/EFFORT_GAPS.md` is complete and that the transcripts covered all three rounds.
4. Look at `results/figures/trajectory_<machine>.png`.
Manual check: NOT VERIFIED (human)

### P5-01 — dfff425
Tests: test_conformance x6. API: conformance.generate_corpus(clone,runner) (oracle generate --locked then pristine_check, else ConformanceError), manifest_jobs/workload_jobs/all_jobs, judge, decode_argv, run_all, summary_rows, disagreement_rows, derive, run. Config [conformance].subjects. make conformance (subjects workloads then run) and make correctness (= conformance for now; later P8 tasks extend). RESULT (M-B, raw correctness/M-B 20261001T060238Z): 2962 streams (2674 generated incl. 9 dictionary + 288 workloads): cf 2962 pass 0 fail; zlib/zng/zrs/zsys all pass; mox 2519 pass, 443 unsupported (gzip, dictionary); 0 failures; 0 disagreements; clone stayed pristine. This supports the B5 claim 'byte-identical output across N streams' with N = 2962 on M-B (M-A not run).

### P5-02 — f02148b
Tests: test_claims x11 (fixtures/results small derived tables+sidecars). API: kits.evidence.Evidence (only via lookup), lookup(table,where,column,results_dir,fmt,transform), table_rows, MissingData, TARGETS; kits.claims.evaluate(results_dir,cfg)->[ClaimResult(id,status,text,evidence,reason)], ORDER of 10 claims (conformance, safety, perf_range, trajectory, similarity, effort, parity_with_zlib, faster_than_zrs, faster_than_mox, gzip_gap_is_hw_crc). provenance.read_table/table_path/sidecar_path take optional results_dir. Config [paper] added. Overreach claims rejected by default; gzip_gap reads framing_hypothesis row machine=ALL column verdict (P6-02). Current repo evaluation: conformance supported, safety supported, effort supported (28.5 h, cost not priced), similarity REJECTED (statement says NOT allowed), perf_range/trajectory pending, overreach rejected (no data), gzip_gap pending.

### P5-03 — 80ea88f
Tests: test_paper_assets x5. API: paper_assets.build_table(results_dir,cfg)->PaperTable(columns,rows[Row(label,cells{cf,zlib,mox}:Cell(display,evidence,status,reason))],footnote).to_markdown(); build_figure(results_dir,out_dir,cfg)->(paths|None,evidence,pending reasons); draw_bars/_bar_data. Config [paper] figure='throughput_unsafe' (or 'trajectory'), figure_corpus/framing/level/mode/subjects, table_opt='3', table_machine='M-B'. 6 rows: Silesia raw L6 oneshot M-A, M-B, gzip ratio M-B (mox n/a), unsafe blocks+fns, runtime deps, stripped binary opt3 M-B. Fixture results dir extended. Figure paper_throughput_unsafe at paper width; PNG inspected.

### P5-04 — 3edde63
Tests: test_paper_kit x6. API: kits.paper.render(results_dir,cfg,out_dir)/rederive/main/source_line/environments; make paper = rederive tables from committed raw then write results/PAPER_KIT.md (byte-identical on rerun, verified). Current kit: 3 supported (conformance 2962/2962 on M-B, safety zero unsafe/zero deps, effort 28.5 h cost not priced), rejected: similarity + 3 overreach (no perf data), pending: perf_range, trajectory, gzip_gap_is_hw_crc; table perf rows pending; figure pending (no figure file committed). Environments section lists M-B CPU/OS from raw env.
Manual check: NOT VERIFIED (human): rerun make paper after full perf/trajectory runs.

### P5-05 — 467e871
Tests: test_clean_clone x4 (fake repos: dirty refused, difference exits nonzero with diff, identical exits zero, missing-file semantics). API: clean_clone.run_check(target, compare, repo, ignore_dirty, sync, keep, out), dirty_paths, committed_bytes; CLI python -m cfbench.clean_clone <target> --compare ... [--ignore-dirty ...]. make paper-check. Real check ran on HEAD: fresh git clone --local --no-hardlinks (hardlinks fail across devices), uv sync --frozen, make paper in ~4 s without third_party/build/toolchain -> results/PAPER_KIT.md IDENTICAL; the paper figure svg is absent in both HEAD and the clone (pending perf data), reported as such. Foundry keeps docs/PROGRESS.md dirty, so my verification used --ignore-dirty docs/PROGRESS.md.

### P5-06 — c1d4af6
Push: git push -u origin HEAD succeeded.
Checklist (verbatim):
1. After the M-A and M-B perf and trajectory runs are committed, run `make paper` and `make paper-check`.
2. Read `results/PAPER_KIT.md`: are the claims conservative, is every claim traced, and is the rejected list complete?
3. Run `make conformance` on M-A and commit it, if a two-machine conformance claim is wanted.
4. Check the figure renders legibly at a 3.3-inch column width.
Manual check: NOT VERIFIED (human)
Note: the current kit has 3 supported claims (target 5-7); the similarity claim is rejected by the generated statement, and the perf/trajectory claims wait for the human data runs.

### P6-01 — 6d3e83b
Tests: test_checksums x5. API: checksums.gib_per_s/build_cells/checksum_argv/value_mismatches/run(cfg,runner,profile,session)/derive(cfg)/main(run|derive). Config [framing] checksum_subjects (7 incl zlib-nohw) and checksum_sizes [64,4096,65536,1048576]. Raw framing/<machine> kind checksums (one file per perf.runs run, shared session); table checksums (pending committed). Quick smoke ok: values agree across subjects; mox crc32 unsupported; quick-run numbers (M-B): crc32 zlib ~3.8 GiB/s, zng/zrs ~12-15 (pclmul), cf ~2.4.
Manual check: NOT VERIFIED (human): full make checksums on M-A and M-B.

### P6-02 — 87be477
Tests: test_framing x6. API: framing.overhead/overhead_rows/control_identical/hypothesis_rows(overheads,cfg,lock)/figure_data/draw/derive(cfg,out_dir,lock)/run. Config [framing] subjects (7), modes ['oneshot'], hypothesis_tolerance 0.25, figure_corpus silesia, figure_level 6. Raw framing/<machine> kind framing-perf variant framing; tables framing_overhead and framing_hypothesis (pending committed; ALL row verdict confirmed/refuted/inconclusive) feed P5-02's gzip_gap_is_hw_crc; figure framing_decomposition. paper rederive now includes framing; PAPER_KIT.md regenerated. Quick smoke showed zlib vs zlib-nohw gzip overhead noise on x86 (identical builds), so only a full run is meaningful.
Manual check: NOT VERIFIED (human): make framing on M-A and M-B.

### P6-03 — 6286605
Push: git push -u origin HEAD succeeded.
Checklist (verbatim):
1. `make framing` on M-A and on M-B (quiet), then commit `data/raw/framing/`.
2. Read `results/framing_hypothesis.csv` and the figure. On M-A, confirm that the zlib-nohw disassembly in `subjects.lock.json` shows no `crc32x`.
Manual check: NOT VERIFIED (human)
Note: on M-B (x86_64) zlib-nohw is identical to the default build, so the hypothesis can only be tested meaningfully on M-A.

### P7-01 — 749834e
Tests: test_infgen x10 (fixtures/infgen real infgen output: stored, fixed, dynamic, zeros, zlib_l9). API: infgen.spec/binary_path/ensure()/count_bytes/parse_lines/summarize(raw,compressed_bytes)/stats(stream_path,framing,infgen). Pinned commit 1e36c3da (v3.6) sha 2d7dac46...; build needs zlib (documented command lacks -lz and fails to link) so uses build/c/zlib or -lz. Stats keys: literals, matches, literal_fraction, match_len_hist/match_dist_hist (dict bins), dist1_fraction, dist1_byte_fraction, dist2_7_fraction, dist2_7_byte_fraction, overlap_fraction, overlap_byte_fraction, blocks{stored,fixed,dynamic}, compressed_bytes, output_bytes, ratio (= compressed/output). Verified on real workloads (output bytes equal original lengths). tools.all_names unaffected (infgen has no 'binary' key).

### P7-02 — 30ec6c4
infgen run over 207 corpus raw streams (tiny excluded); raw data/raw/content/any records workload manifest SHA-256. results/content_features.csv has one row per workload/level/framing; token features come from the raw-framed stream and are copied to zlib/gzip rows (framing_analysed column), ratio from each framing's own size. Added mean_match_len to infgen.summarize, make content-features, content alias replacing the stub. make lint and make test pass (301 tests).

### P7-03 — 08eed8f
cfbench/content/correlate.py: joins cf generic oneshot ratio_vs_zlib with content_features; scipy Spearman (scipy pinned in uv.lock) with seeded permutation p (content.permutations=10000 from run.seed). Verdict per machine, weaker of H1's two features, machine disagreement gives inconclusive. Table content_hypotheses and results/CONTENT_FINDINGS.md written; with no perf data both are pending and inconclusive. Scatter figures content_scatter_<feature>_<machine> render only with perf data. make content = content-features then correlate (rerunning features adds a new raw file; I committed only the first). 307 tests pass.

### P7-04 — 20ba3b9
Manual check: NOT VERIFIED (human)
Checklist for B7:
1. Once full perf data exists for both machines, rerun `make content` and read results/CONTENT_FINDINGS.md and the scatter plots (rerunning adds a new raw content file; keep one).
2. Sanity-check the infgen statistics for kennedy.xls and ptt5 by hand (results/content_features.csv).
Current state: content_features.csv is real data (207 rows); content_hypotheses is pending and inconclusive until perf data exists. Push happens at run finish.

### P8-01 — 66b8c24
cfbench/malformed.py runs 42 malformed files x 6 subjects (oneshot decode, conformance.subjects) on M-B. Framing from directory; outcome accept, accept+trailing, error:<kind>, unsupported; disagreement = accept vs reject among supported subjects. 4 disagreements, all cf rejecting trailing data or a bad second gzip member that every other subject accepts (by SPEC design, default TrailingData::Reject). cf matches EXPECTED.tsv on all files so no findings.md entry (findings.md carries a marked block regenerated by derive). Note: zlib-family subjects report trailing_bytes 0 even for trailing input, so accept+trailing is rare. make malformed added; correctness depends on it. 312 tests pass.

### P8-02 — 35fd43e
fuzz/ is its own workspace (crate cfbench-fuzz, lib cffuzz): targets diff_cf_zlib, diff_cf_zrs, diff_cf_mox. zlib linked from build/c/zlib/lib/libcfbz_default.a via fuzz/build.rs; zrs =0.6.8, mox =0.9.1, cf pinned to round-3 rev. Outcome is Ok(bytes), Rejected or Capped; compare() is the agreement rule. Gzip interpretation: cf decodes all members, so zlib-family references loop members (reset while input starts 1f 8b). cf runs TrailingData::Allow. Normalizations listed in fuzz/README.md. make fuzz-build = fmt check, cargo +nightly test (3 tests), cargo +nightly fuzz build. An 8 s sanity run of each target found no divergence (not recorded). .gitignore gained /fuzz/corpus and /fuzz/artifacts.

### P8-03 — 0b89382
cfbench/fuzzing.py: seeds (level-6 workloads plus malformed files, framing byte 0/1/2; mox skips gzip) go to fuzz/corpus/<t>; runs cargo +nightly fuzz run -fork=<jobs> -ignore_crashes=1 -max_total_time=budget*3600/jobs -seed; parses stat::number_of_executed_units (or last #N in fork mode), exec/s, cov/ft, crash count and artifact paths; cargo fuzz cmin; tar.gz of corpus and artifacts via rawio.blob_path, sha256 in the raw JSON (kind fuzz). New config [fuzz] and quick override jobs=1; make fuzz and make fuzz-smoke. Fixtures: real fork-mode log plus a hand-trimmed crash excerpt in libFuzzer's documented format. Smoke run (60 s, data/smoke only, not committed): zlib 18406 execs 0 divergences, zrs 5459 execs 0, mox 6826 execs 6 divergences (artifacts left in fuzz/artifacts/diff_cf_mox for P8-04). 316 tests pass.
