# Review: build/2026-10-01
Round: 1

**Verdict: CHANGES REQUESTED**

Scope: the whole branch `e17e6973d7a7..30635db` (71 tasks, all marked done, none blocked or skipped). I read every task commit's stat and the diffs of the harness, subjects, orchestration, statistics, reports, kits, fuzz and bomb modules, checked them against SPEC and PLAN, ran `foundry_verify`, and ran 16 mutations through `foundry_mutate`.

Verify result: all 10 mechanical constraints pass with no fixture failures and no hits. `make lint` passes. `make test` fails: 5 failed and 4 errors, all in throwaway-repo tests (see F-1). Because the baseline is red, `foundry_mutate` reports every mutant as "killed". I read each result's pytest summary and counted a mutant as killed only if a test failed beyond those 9 baseline failures. Four mutants survived on that reading.

## Findings (most severe first)

### F-1 [Tests / verify red] Throwaway-repo tests depend on the user's global git config, so `make test` fails
- Where: `tests/test_clean_clone.py:8-12` (the `git()` helper, used by `make_repo` at :23 and :90), and the matching commit helper in `tests/test_cleanflate_src.py`.
- What is wrong: the helpers run `git commit` in `tmp_path` repos and inherit the user's global `commit.gpgsign=true` and signing program. While the signing agent is down, every such commit fails ("1Password: Could not connect to socket"). That gives 5 FAILED and 4 ERROR in `make test`. With `GIT_CONFIG_*` overrides disabling signing, all 11 tests pass. HANDOFF records this but calls it environmental. It is a test-hermeticity defect: whether the suite passes depends on the reviewer's `~/.gitconfig`.
- What breaks: `make test` (a verify command) is red, so the task-level "every task leaves make test green" convention fails. It also makes `foundry_mutate` unusable without reading results by hand.
- Fix: isolate the git subprocesses in these tests from global and system config. One way is an autouse fixture that sets `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`. Another is passing `-c commit.gpgsign=false -c tag.gpgsign=false` in the helpers.
- Task: P5-05, P10-06 (clean_clone tests) and P0-03 (cleanflate_src tests).

### F-2 [Spec drift + Tests] `decode --mode oneshot` always reports `trailing_bytes: 0` and `consumed = input.len()`, so the malformed matrix can never show `accept+trailing`
- Where: `crates/harness/src/cli.rs:378` (`r.consumed = input.len() as u64;`; trailing is never set). The cause is `Subject::oneshot` in `crates/harness/src/subject.rs`, which returns only the produced length. The consumer is `cfbench/malformed.py:54` (`outcome`).
- What is wrong: SPEC §3.6 asks for error vs accept plus bytes produced. PLAN P8-01 requires a separate `accept+trailing` outcome. Reproduced with `hello.zlib` plus one byte: `cfb-zlib`, `cfb-zrs` and `cfb-mox` in oneshot mode report `consumed: 45, trailing_bytes: 0`. Stream mode on the same input correctly reports `consumed: 44, trailing_bytes: 1`. The committed `results/malformed_matrix.csv` therefore has zero `accept+trailing` rows, even for `rfc1950/trailing_byte.bin` and `rfc1952/trailing_garbage.bin`. Those files show plain `accept`, and that wording has spread into `MALFORMED_HIGHLIGHTS.md`, `RESULTS.md`, `BLOG_NOTES.md` and `TALKING_POINTS.md`.
- Test gaps found by mutation:
  - Deleting cf's oneshot trailing-data check (`crates/subj-cf/src/main.rs`, the `if !inp.is_empty()` block) **survived**. Nothing tests that cf rejects trailing data, and that rejection is the mechanic behind all four committed disagreements.
  - Setting `trailing_bytes: 0` in the zlib-API stream path (`crates/zlibapi/src/lib.rs`) **survived**.
  - `tests/test_malformed.py::test_trailing_accept_is_distinguished` only feeds synthetic dicts to `outcome()`.
- What breaks: a T3 finding (the malformed-input disagreements) is reported less precisely than PLAN requires. A comparator that silently ignores trailing bytes is indistinguishable from a clean accept.
- Fix:
  - Make oneshot report the input bytes actually consumed (for example, `Subject::oneshot` returns produced and consumed), and have `decode` report `consumed` and `trailing_bytes` truthfully for every subject.
  - Add subject-level tests with trailing input in both modes.
  - Re-run `make malformed` (deterministic, M-B, data-run protocol) and regenerate the kits.
- Task: P0-05 / P8-01 (plus P0-06, P0-07, P0-08 for the subjects).

### F-3 [Constraint (read-only rule) + Spec drift] RESULTS.md comparison tables lack the parity footnote, and the methodology misstates the load precondition
- Where: `cfbench/kits/results_md.py:495` (`table_block`), `:162` and `:996`.
- What is wrong:
  - CLAUDE.md says every table and figure carries the §2.4 parity note, and SPEC §2.4 says the note "must accompany every comparison table". In `results/RESULTS.md` the note appears only under figure captions and in one threats paragraph. None of the 21 tables carries it. Examples are conformance per subject (line 85), binary size (132), unsafe (192), similarity positioning (265), and the per-file perf tables once data exists.
  - RESULTS.md says "A run is refused when the starting load average exceeds 1.0" (methodology) and "runs are refused above a starting load of 1.0" (threats). `cfbench/perf.py` only warns unless `--strict` is passed, and `make perf` never passes it (PLAN P0-11 says warnings, never refusal).
  - The methodology line "Streaming uses 4096-byte and 1048576-byte chunks" mixes `small_out_chunk` with `large_in_chunk` and omits the 1 KiB input chunk.
- What breaks: the T3 kit misdescribes the method it reports, and its comparison tables break the parity rule.
- Fix: append the parity footnote to every comparison table that `table_block` (and any other table emitter) renders. Restate the load precondition as a recorded warning (refused only with `--strict`). State small (in/out) and large (in/out) chunk sizes correctly. Regenerate RESULTS.md.
- Task: P10-03, P10-04.

### F-4 [Tests / constraint enforcement] Evidence checks for kit numbers accept substrings, so fabricated numbers pass
- Where: `cfbench/kits/pitch.py:39` (`not any(token in a for a in allowed)`) and `tests/test_paper_kit.py:79` (`run in displays`, where `displays` is one joined string).
- What is wrong: CLAUDE.md says kits print numbers only through `Evidence`, and these checks are its enforcement. Both match substrings. Verified: `check_bullet(Bullet("cf is 9 times faster than zlib on 35 files", (), ("0.935",)))` passes. "9" and "35" are accepted because they occur inside "0.935". The same weakness applies to every PITCH_KIT and BLOG_NOTES bullet and to the paper-kit test.
- What breaks: an invented small number in a talking point or claim would not be caught.
- Fix: compare whole number tokens (same `_NUMBER` tokenisation on both sides) against the set of evidence and label tokens. Keep the hyphen/SHA-256 exclusion.
- Task: P10-02, P10-05, P5-04.

### F-5 [Tests] Hypothesis thresholds are untested at their boundaries
- Where: `cfbench/framing.py:124` and `cfbench/content/correlate.py:91-93`.
- What is wrong, both found by mutation:
  - Widening the framing band to `10 * tol` **survived**. The only "outside band" fixture has a relative difference of about 12.5, so `hypothesis_tolerance` is never exercised near its value.
  - Removing the `abs(rho) >= min_abs_rho` condition from the H1/H2 confirmed rule **survived**.
- What breaks: the Hypothesis protocol says verdicts are decided by the config thresholds, but nothing would notice if those thresholds stopped being applied.
- Fix: add boundary tests:
  - framing: |rel_diff| just inside and just outside `hypothesis_tolerance`.
  - content: p < alpha with |rho| between `null_abs_rho` and `min_abs_rho` gives inconclusive; |rho| < `null_abs_rho` gives refuted; positive rho with p < alpha gives refuted.
- Task: P6-02, P7-03.

### F-6 [Constraint (read-only rule)] The binary-size figure draws a missing value as a zero-height bar
- Where: `cfbench/more_charts.py:118` (`d.get(opt, 0) / 1024`).
- What is wrong: CLAUDE.md says unsupported or missing cells are "n/a", never zero. If a subject lacks one opt-level (for example a failed build, so empty `bytes`), the chart draws a 0 KiB bar. Current M-B data has every value, so the committed figure is unaffected; the defect is latent.
- Fix: skip the bar and draw an "n/a" label for a missing (subject, opt) slot. Test it with a fixture table that lacks one opt-level.
- Task: P10-01.

### F-7 [Spec drift] The bomb table's `ratio` for nested-layer rows is the overall ratio, not the per-layer ratio
- Where: `cfbench/bombs.py:154` (`"ratio": c.get("overall_ratio") or ratio(...)`).
- What is wrong: PLAN P8-05 and Spec issue 4 say the sweep "reports per-layer and overall ratios". Each layer row shows the overall gzip-of-gzip ratio (about 1e6 at full size) under `ratio`. A reader would attribute that ratio to decoding that single layer. The per-layer ratio appears nowhere in the table.
- Fix: make `ratio` the layer's own output/compressed ratio and add an `overall_ratio` column (empty for single-layer cases). Update the pending table header and any RESULTS.md renderer that names the bomb columns.
- Task: P8-05.

### F-8 [Spec drift (PLAN)] `make paper-data` does not exist
- Where: `Makefile`, PLAN Decisions (line 16) and PLAN Spec issue 11.
- What is wrong: the PLAN resolves SPEC §4's "make paper (T1 only, fastest path)" against B5 by splitting rendering (`make paper`) from measuring (`make paper-data`: "runs the T1 measurements for the current machine"). Only the render half exists. `make help` and README do not mention it.
- Fix: add `paper-data` with the machine-specific T1 measurements as prerequisites (env, pins, perf, trajectory, size, conformance), then `$(MAKE) paper`. List it in `make help` and README.
- Task: P5-04 / P10-06.

## Mutation sample (16 mutants)
- **Killed:** `timing.rs` calibration, `perf_report` aggregate file-set check, `agreement` aggregate flagging, `similarity.summary` "no metric separates" branch, `conformance.judge` SHA check, `claims._conformance` disagreement check, `effort.history` idle-gap rule, `perf.shuffled` per-run seed, `pins` aarch64 CRC regex.
- **Survived:** `subj-cf` oneshot trailing-data rejection (F-2), `zlibapi` stream `trailing_bytes` (F-2), `framing` tolerance band (F-5), `correlate` `min_abs_rho` (F-5).

## Interpretation choices (HANDOFF and PROGRESS)
- Bombs compressed with Python's streaming zlib: accepted. cfb-zlib cannot stream 4 GiB, and the bytes are not claimed byte-identical (see Notes on recording the Python zlib version).
- Bomb RSS floor (`rss_floor_bytes`): accepted and documented.
- miniz_oxide Adler-32 check re-done in the fuzz harness under `--cfg fuzzing`: accepted. It is correct, and it is needed for the oracle to be meaningful.
- tokei embedded-Markdown rows: accepted.
- Fuzz gzip normalisation (zlib-family reference loops members instead of cf decoding one member): accepted. PLAN let the implementer choose and document it, and `fuzz/README.md` does.
- RESULTS.md tables copied from derived tables with a per-table source line, rather than one `Evidence` per cell: accepted. Each table names its table, raw files and script, which meets SPEC §6. The missing parity note on those tables is F-3.
- `zlibapi` and zng linking via `rustc-link-arg-bins` instead of `link-lib=static`: accepted. It is documented, and the version tests prove the right library is linked.

## Blocked and skipped tasks
None.

## Spec issues
No new ones. PLAN's Spec issues 1–13 still stand. Issue 6 (x86_64 hardware-CRC control identical to default) and issue 7 (cross-language positive control) visibly shape the current results: every n-gram metric reports "controls not separated".

## Manual checks still owed (from HANDOFF.md)
1. Timing-sensitive full runs on a quiet machine, M-A and M-B: `make perf perf-native framing trajectory`, then `make content`. All their tables are pending.
2. `make fuzz` (3 targets x 4 CPU-hours) and `make bombs` (4 GiB cases).
3. M-A runs of env, conformance and malformed (and `make fetch c-subjects subjects pins` for the M-A `subjects.lock.json` entry).
4. Fill in prices in `config/pricing.toml`, and fragment verdicts in `config/similarity_verdicts.toml`.
5. Review `results/STRUCTURE_COMPARISON.md`, `RESULTS.md` (threats to validity), `PITCH_KIT/TALKING_POINTS.md` and `BLOG_NOTES.md`.
6. Re-sign commits made with `commit.gpgsign=false` after P10-02, if signed history is required.

## Notes (not findings)
- `fuzz/src/lib.rs` `decode_mox` allocates and zeroes a 64 MiB buffer per fuzz input. That likely explains mox's much lower exec/s in the smoke run. Reusing a buffer would let the 4 CPU-hour budget go further.
- The mox Adler-32 normalisation in `fuzz/src/lib.rs` cannot be covered by `fuzz/tests`, which build without `--cfg fuzzing`. That is acceptable, but worth a comment in the test file.
- `bombs.py` does not record `zlib.ZLIB_RUNTIME_VERSION` for the Python-compressed bombs. Adding it to the raw payload would close the provenance loop.
- RESULTS.md prints "Pending: run `make fuzz` on M-A and M-B." twice in a row (fuzz_stats and fuzz_divergences).
- BLOG_NOTES "The clean-room setup" states "cleanflate was built from the RFC texts alone" as fact, next to a similarity statement that does not allow the independence claim. The human author may want to soften it to "under clean-room rules".
- `agreement.compare_session` only compares cells that succeeded in both runs. A cell that fails in one run is not flagged there, though `perf_report` marks it as an error and the aggregate as incomplete, so claims stay safe.
