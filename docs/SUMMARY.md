# Build summary: build/2026-10-01

**Merge line:** `build/2026-10-01`, base `e17e6973d7a7` → head `41dab22`, 188 commits, 4 reviews, final verdict **APPROVED** (review 4).

83 of 83 tasks done (71 planned, 12 review fixes), 0 blocked, 0 skipped. At review 4, `make lint` and `make test` (389 Python tests plus the Rust tests) were green, and all 10 mechanical constraints passed.

## What was built

**Phase 0: scaffolding and pins (P0-01 to P0-13).** A Python 3.12 / `uv` orchestration package (`cfbench/`), a config loader and a Makefile skeleton. Machine detection and environment capture, plus raw-data I/O. A read-only pinned clone of cleanflate with a pristine check. Pinned C builds of zlib 1.3.2, a zlib control build with hardware CRC disabled, and zlib-ng 2.3.3. A custom Rust timing harness with allocator accounting. Seven subject binaries: cf, zlib, zlib-nohw, zng, zrs, mox and zsys. Hardware-CRC determination, `subjects.lock.json`, 288 generated workload streams, the perf orchestrator with a smoke bench, and a smoke similarity run.

**Phase 1: core performance (P1-01 to P1-07).** Statistics: median and a seeded bootstrap CI. Derived tables that track their provenance: per-cell perf, ratios against zlib, per-corpus aggregates and tiny inputs. The run-to-run agreement check, a `target-cpu=native` Rust variant, and the throughput chart helpers.

**Phase 2: size and safety (P2-01 to P2-06).** Pinned third-party tools. Minimal stdin-to-stdout decompressors used to measure binary size, plus cargo bloat. The unsafe surface of each subject, its dependencies and its audit status.

**Phase 3: similarity with controls (P3-01 to P3-08).** One decompression-path manifest scopes both similarity and LOC. Metrics: token n-gram Jaccard over a cross-language vocabulary, identifier and comment overlap, and JPlag for same-language pairs. Top-20 fragment pairs carry persistent human verdicts. Each pair is positioned against the negative and positive controls, and a generated statement says whether an independence claim is allowed. A structural comparison write-up closes the phase.

**Phase 4: trajectory and effort (P4-01 to P4-07).** cf is built at each of the three cleanflate release rounds, and the trajectory is run and charted. Effort comes from git history, the tool log and Foundry state. Token usage is exported from transcripts without their content. Cost uses `config/pricing.toml`, which is still unset. The phase adds zlib-rs status-quo context and effort tables with a documented gaps file.

**Phase 5: PAPER_KIT (P5-01 to P5-06).** A conformance runner (cf passes 2962/2962 on M-B). A claims engine whose numbers carry evidence links. The paper table and figure, the PAPER_KIT renderer with `make paper`, and a clean-clone regeneration check.

**Phase 6: framing decomposition (P6-01 to P6-03).** Checksum microbenchmarks, the framing-overhead decomposition, and the hardware-CRC hypothesis verdict with its figure.

**Phase 7: content analysis (P7-01 to P7-04).** An infgen build and parser, and content features for every corpus workload (207). Spearman correlation decides the H1 and H2 verdicts, with scatter plots and findings. H1 and H2 stay pending until the perf data exists.

**Phase 8: correctness depth (P8-01 to P8-06).** A malformed-input behaviour matrix: 4 of 42 files split the subjects, and cf is the stricter one in all 4. Three differential `cargo fuzz` harnesses (cf against zlib, zrs and mox), with orchestration, statistics, coverage and divergence triage. A decompression-bomb sweep that uses nested gzip to reach a ratio of at least 1:1,000,000.

**Phase 9: complexity and remaining size metrics (P9-01 to P9-04).** Decompression-path LOC with tokei. Complexity distributions for Rust (rust-code-analysis) and for C (lizard), combined into the complexity table.

**Phase 10: kits (P10-01 to P10-07).** The remaining figures, PITCH_KIT with talking points, RESULTS.md in two parts (the second includes threats to validity), and BLOG_NOTES.md. Also `make all`, and a clean-clone check that every kit regenerates byte-identically (`make kits-check`).

**Review fixes (R1-01 to R1-08, R2-01, R3-01 to R3-03).**
- Throwaway-repo tests no longer depend on the user's git config.
- One-shot decode now reports the bytes it really consumed and any trailing bytes. The malformed matrix was re-run with these numbers.
- RESULTS.md tables now carry the parity footnote.
- Kit numbers must match evidence as whole tokens; substring matches no longer pass.
- Hypothesis thresholds get boundary tests.
- The binary-size figure shows a missing value as "n/a".
- The bomb table reports per-layer and overall ratios separately.
- `make paper-data` was added.
- Makefile prerequisites were fixed so measurement targets can run from a fresh clone.
- New harness and subject tests cover per-iteration timing, allocator free/realloc accounting, and one-shot "output full" handling.

## Decisions that shaped it

From PLAN.md Decisions:
- (plan) Phases map 1:1 to SPEC milestones B0 to B10. The one exception: the conformance runner moves to Phase 5.
- (plan) Orchestration is Python 3.12 via `uv`. Rust is used only for the timed harness and the subject shims.
- (P0-05) A custom Rust timing harness replaces criterion, because cells must be shuffled across separate subject binaries. Python computes the median and the bootstrap CI.
- (P0-06 to P0-08) Each subject is its own binary, with one process per cell in seeded random order. zlib, zlib-nohw and zsys share C symbols, so they cannot share a process.
- (P0-03, P0-04) Pins: zlib 1.3.2, zlib-ng 2.3.3 (native `zng_` API), `libz-rs-sys =0.6.8`, `miniz_oxide =0.9.1` (no `simd`), Rust 1.89.0, a fixed infgen commit, and JPlag 6.3.0.
- (P4-01) "Round" means a cleanflate release tag (v0.1.0, v0.2.0, v0.3.0-cleanroom), never a Foundry review round.
- (P0-03) cleanflate is consumed as a Cargo git dependency pinned by `rev`, plus a read-only clone at the round-3 SHA. A pristine check runs after every step that writes to the clone.
- (P0-05) One-shot mode means fresh state, a single decode call, and an output buffer of exactly the decompressed length. Streaming uses 1 KiB in / 4 KiB out (small) and 1 MiB in / 1 MiB out (large).
- (P0-06) mox gzip cells are recorded as `unsupported`. There is no hand-rolled gzip wrapper.
- (P0-10) Workloads are compressed by stock zlib with gzip os=255 and mtime=0, so they are byte-identical across machines. Tiny inputs are prefixes of 3 corpus files.
- (all phases) The implementer commits only deterministic, non-timing data from M-B. Timing runs, and every run on M-A, are left to a human on a quiet machine.
- (P5-04, R1-08) `make <category>` measures, then derives. `make paper`, `make pitch` and `make blog` render from committed data. `make paper-data` measures the T1 data.
- (P1-04) `make perf` does 2 runs in one session. The agreement check compares per-run medians, and the reported numbers pool the samples of both runs.
- (P0-04, P0-09) zlib-nohw is built with `-U__ARM_FEATURE_CRC32` on aarch64. On x86_64 it is identical to the default build. Disassembly is the deciding evidence.
- (P3-02 to P3-04) The primary similarity metric is token n-gram Jaccard. Identifier and comment overlap cover every pair. JPlag covers same-language pairs only. Dolos is not used.
- (P3-01, P9-01) One decompression-path manifest scopes both similarity and LOC.
- (P3-06) A pair's position between the controls is (score − negative) / (positive − negative). "Near the negative control" means a position ≤ 0.25. If the controls are not separated, that metric cannot support a claim.
- (P6-02) The framing hypothesis is confirmed if cf's overhead is within ±25% (relative) of zlib-nohw's on both machines. It is refuted if outside that band on both. Anything else is inconclusive.
- (P7-03) H1 and H2 use Spearman's rho with a permutation p-value. Confirmed: |rho| ≥ 0.5, p < 0.05 and the expected sign. Refuted: the opposite sign at p < 0.05, or |rho| < 0.2. Anything else is inconclusive.
- (P4-03, P4-04) Effort data comes from transcripts, as an export with no content. Prices ship as `null`, so cost is a documented gap rather than an invented number.
- (P5-03) The paper figure is a cf/mox/zlib throughput bar chart annotated with unsafe counts. Setting `paper.figure` switches it to the trajectory chart.
- (P8-05) The bomb sweep reaches a ratio of at least 1e6 with two nested gzip layers, and reports per-layer and overall ratios.
- (P2-02) The minimal programs decode zlib framing. zsys is excluded from binary size because it is a dynamic system library.
- (plan) The plan is fully serial, with no parallel streams.
- (plan) Every SPEC numeric default is a key in `config/bench.toml`, never a literal in code.
- (plan) Open tool questions are handled inside their tasks by the tool-gap protocol.

Interpretation choices (HANDOFF / PROGRESS / REVIEW):
- (P0-02) `on_ac` is null on a desktop. cleanflate fields are read from `rounds.json` `primary_round`.
- (P0-07) C libraries are linked with `rustc-link-arg-bins=-l<lib>`, because `link-lib=static` puts them in the wrong order. Trailing gzip members are not looped in the zlib-API subjects.
- (P3-05) Fragment windows with more than 50 occurrences count as boilerplate and are skipped; the skip counts are recorded. The uncapped run took about 7 minutes.
- (P8-02) mox skips its Adler-32 check under `--cfg fuzzing`, so the fuzz harness verifies the checksum itself. For gzip, the zlib-family references loop over members to match cf, which decodes all members.
- (P8-05) Bombs are compressed with Python's streaming zlib at level 9, because `cfb-zlib` reads its whole input into memory. Bomb RSS includes the launcher's RSS as a floor (`rss_floor_bytes`, about 19.5 MB).
- (P9-01) tokei reports Rust doc comments as embedded Markdown rows, so they appear as `<language> (embedded)` rows.
- (P10-03) RESULTS.md tables are copied from the derived tables, with a source line per table, instead of one `Evidence` object per cell.
- (R1-01) Git isolation lives in the test helpers rather than an autouse fixture, so a test can still set a hostile config.
- (R1-02) The harness's test `IdentitySubject` treats a NUL byte as the end of a stream, so tests can produce trailing input.
- (R3-01 / R3-03) The lower bound of the alloc test was loosened to `BIG - SLACK` after a flake caused by concurrent frees. The realloc mutant is still killed.
- (R3-02) The output-full tests use zlib framing only. The output-full arm does not depend on framing.

## Assumptions still in play

None. SPEC has no `⚠️ ASSUMPTION` markers, so there were no tuning tasks. Every numeric default SPEC states is a key in `config/bench.toml` and has its SPEC value. `config/pricing.toml` (unset) and `config/similarity_verdicts.toml` (empty) are human inputs, not assumptions.

## Spec issues (edits to make to SPEC.md)

1. §2.3 cites §3.4 for unsafe inspection; it should cite §3.7.
2. B0 acceptance requires M-A builds, but the implementer runs only on M-B. State that M-A builds and runs are manual checks.
3. §5 T1 needs conformance, but conformance is in B8, after the paper kit (B5). Move the conformance runner to B5.
4. §3.6 asks for bomb ratios ≥1:1,000,000, but one DEFLATE stream tops out near 1032:1. Allow nested gzip and specify per-layer and overall ratios.
5. miniz_oxide has no gzip framing. State that mox gzip cells are `unsupported` and are shown as "n/a".
6. Stock zlib has no x86_64 hardware-CRC path, so on M-B the "hardware CRC disabled" control is identical to the default build. The §3.3 hypothesis is informative only on M-A. This visibly shapes the results.
7. The §3.8 positive control (zrs↔zng) is cross-language, while the other pairs are Rust↔Rust. Every n-gram metric reports "controls not separated". Consider a same-language positive control.
8. §3.9 asks for the time spent on human interventions, but the provenance file has no durations. Drop the requirement or require durations.
9. §3.9 asks for zlib-rs's "stable-API release", but zlib-rs has no 1.0. Reword it as "first publication".
10. Token prices are not given. Add a pricing source, or accept cost as a gap.
11. §4 calls `make paper` the "fastest path", while B5 requires it to regenerate from a clean clone. Document the split between `make paper` (render) and `make paper-data` (measure).
12. The full §3.2 matrix takes hours per machine. State that full timing runs are human-run.
13. Define "Canterbury" as the standard 11-file corpus.

The review rounds added no new spec issues.

## Manual checks owed

- **Phase 0 / all phases:** run the M-A builds: `make fetch c-subjects subjects pins` for the M-A `subjects.lock.json` entry. Look for every subject building on macOS arm64, and for zlib-nohw's disassembly showing no `crc32[bhwx]`.
- **Phases 1, 4, 6, 7:** on a quiet machine, on both M-A and M-B, run `make perf perf-native framing trajectory` (or `make paper-data` for T1), then `make content`. Look for the agreement check passing within ±5%, and for the framing hypothesis and H1/H2 verdicts being filled in rather than pending.
- **Phase 3:** fill in fragment verdicts in `config/similarity_verdicts.toml`. Review `results/STRUCTURE_COMPARISON.md`. The generated statement currently says the T1 independence claim is NOT allowed.
- **Phase 4:** fill in prices in `config/pricing.toml`. Cost is unavailable until then.
- **Phase 5 / 8:** run env, conformance and malformed on M-A. Look for cf matching `EXPECTED.tsv` and for any new split between subjects.
- **Phase 8:** run `make fuzz` (3 targets × 4 CPU-hours) and look for zero untriaged divergences. Run `make bombs` (the full 4 GiB sweep) and look for an overall ratio of about 1e6 and `limit_hit` being enforced for every subject.
- **Phase 10:** review `RESULTS.md` (threats to validity), `PITCH_KIT/TALKING_POINTS.md` and `BLOG_NOTES.md`. Consider changing "accept" to "accept+trailing", and softening "built from the RFC texts alone". Run `make kits-check` after committing, because it refuses a dirty tree.
- **R2-01 / R3-03:** run `make paper-data`, `make framing` and `make fuzz` from a real fresh clone, which needs network. NOT VERIFIED.
- **Signing:** commits after P10-02 were made with `commit.gpgsign=false`. Re-sign them if signed history is required.

## Review history

- Review 1: 8 findings, 8 fix tasks (R1-01 to R1-08), CHANGES REQUESTED. First review, so no recurrence.
- Review 2: 1 finding, 1 fix task (R2-01), CHANGES REQUESTED. **Recurred:** P10-06 was named in review 1 (F-1, F-8) and again in review 2 (F-1, together with the R1-08 `paper-data` fix).
- Review 3: 3 findings, 3 fix tasks (R3-01 to R3-03), CHANGES REQUESTED. Flagged **non-converging**. No task id from review 2 recurred, but F-3 (`framing`, `fuzz` and `fuzz-smoke` lacking `workloads`) reopened R2-01's Makefile-prerequisite fix.
- Review 4: 0 findings, 0 fix tasks, **APPROVED, with notes only**. The notes were flagged but not queued as work:
  - P0-05 timing test `calibrates_iterations_to_min_sample_time` flakes under load. The per-sample floor is not guaranteed after preemption during calibration. Measured failure rates: about 1 in 240 runs alone, and about 10 in 800 under 8-way overload. A suggested fix is to drop or loosen that floor.
  - Granular `similarity-*`, `effort` and `size` targets fail loudly without `fetch` or `c-subjects`.
  - `cfbench/fuzzing.py:91` skips missing streams.
  - The "accept" vs `accept+trailing` wording in BLOG_NOTES and TALKING_POINTS.
  - A dead `if !inp.is_empty()` check in `Cf::oneshot`.
  - Per-section parity reminders in `STRUCTURE_COMPARISON.md`.
  - From review 1: mox's 64 MiB per-input fuzz allocation, and `bombs.py` not recording Python's zlib version.

## Pipeline friction

- implement / tool-refusal: The 1Password SSH signing agent died mid-run. Test suites that commit in throwaway repos (clean_clone, cleanflate_src) failed under `foundry_verify` because they used the global gpgsign config. The workaround was `commit.gpgsign=false` locally, but verify's `make test` could not be made green from the tool side.
- review / verify-baseline-red: `make test` was red when review started: 9 throwaway-repo tests failed because the signing agent was down. `foundry_mutate` then reported every mutant as killed, so each result had to be read by hand to tell real kills from baseline failures.
- review / tool-access: The round-3 fix tasks named "`foundry_mutate` ... reports killed" as their verification, but `foundry_mutate` was not available to the implementer. It applied and reverted mutants by hand, and the reviewer had to re-run every one. Also, `foundry_mutate` does not serialise concurrent calls: two parallel calls ran `make test` against each other's mutated files.
