# Review: build/2026-10-01
Round: 3

**Verdict: CHANGES REQUESTED**

Scope: the whole branch `e17e6973d7a7..b234b3a` (80 tasks, all done, none blocked or skipped). Rounds 1 and 2 reviewed every original task commit and every R1 fix. This round:
- reviews R2-01 (`4139c19`) against its PLAN entry and SPEC §4 / B10;
- widens the mutation sample to modules the earlier rounds never mutated, mainly the Rust harness and the subject crates.

Verify result:
- `foundry_verify`: all 10 mechanical constraints pass, with no fixture failures and no hits.
- `make lint` is green. `make test` is green (375 Python tests plus the Rust tests).

## R2-01 status

The fix is correct as far as it goes:
- `perf`, `perf-native`, `smoke-bench` and `trajectory` now depend on `workloads`, and `malformed` depends on `fetch`.
- `make -n all`, `make -n paper-data` and `make -n smoke` all print `cleanflate_src fetch`, then `workloads generate`, before the first `perf run`.
- Three mutants were killed by `test_measurement_targets_depend_on_their_inputs`: dropping `workloads` from `trajectory`, dropping it from `smoke-bench`, and dropping `fetch` from `malformed`.
- The test is hermetic: it parses the Makefile and runs `make -n` only, and recursive `$(MAKE)` lines inherit `-n`.
- No interpretation choices were logged, and none were needed.

What it missed is F-3 below.

## Findings (most severe first)

### F-1 [Tests: P0-05] The harness's per-iteration normalisation and its allocator free/realloc accounting are untested
- Where:
  - `crates/harness/src/timing.rs:49` (`samples_ns.push(t.as_nanos() as f64 / iters as f64)`)
  - `crates/harness/src/alloc.rs:42` (`sub` in `dealloc`) and `:48` (`sub` in `realloc`)
  - Tests: `crates/harness/tests/timing.rs:12-30` and `crates/harness/tests/alloc.rs`.
- What is wrong: three mutants survived `make test`.
  1. Dropping `/ iters as f64` from `timing.rs:49` survives. `calibrates_iterations_to_min_sample_time` asserts lower bounds only (`sample_ms >= 0.5 * min_sample_ms` and `s >= 90 µs`). A sample that is `iters` times too large passes both.
  2. Deleting `sub(layout.size())` from `dealloc` survives. Neither alloc test checks `current_bytes()` after a large free; the `< SLACK` check only sees the 1 MB `c_zalloc` block.
  3. Deleting `sub(layout.size())` from `realloc` survives. No test grows an allocation.
- What would break:
  - Every MiB/s, ns/byte and ratio-vs-zlib number in SPEC §3.2 is computed from `samples_ns`. A regression in mutant 1 would inflate them by a factor of `iters_per_sample` (often 2 to 1000+), and no test would notice.
  - `peak_heap_bytes` (a SPEC §3.2 metric) is `peak - current` across the heap pass. Mutants 2 and 3 would turn it into cumulative allocated bytes; for streaming subjects whose output buffers grow by `realloc`, that overstates it many times over.
  - The code is correct today. The acceptance tests that P0-05 names just do not fail when these mechanics are removed.
- Fix: tests only, in `crates/harness/tests/`.
  - **Timing:** a test with `warmup_ms = 0`, `min_samples = 20`, `min_sample_ms = 2` and a ~100 µs spin op. Time the whole `measure` call with `Instant`, then assert:
    - `iters_per_sample >= 2`
    - `sum(samples_ns) * iters_per_sample <= total_elapsed_ns`

    The sampled time is a subset of the call, so this holds under any machine load. It fails by a factor of ≥ 2 on mutant 1.
  - **Allocator:** a test under the existing `LOCK`. Let `base = current_bytes()`.
    - `Vec::<u8>::with_capacity(BIG / 2)`, then `reserve_exact(BIG)`, which forces a `realloc`.
    - Assert that `current - base` is in `[BIG, BIG + SLACK)`. This kills mutant 3 (current becomes 1.5 × BIG).
    - Drop the vector and assert `current - base < SLACK` (use signed arithmetic). This kills mutant 2.
- Task: P0-05.

### F-2 [Tests: P0-06, P0-07, P0-08] No test exercises a real subject's one-shot "output buffer full" result, which the harness's grow-and-retry and `limit_hit` logic depend on
- Where:
  - Subjects: `crates/subj-cf/src/main.rs:104`, `crates/zlibapi/src/lib.rs:321-323`, `crates/subj-mox/src/main.rs:68-70`, `crates/subj-zrs/src/main.rs:140` and `crates/subj-zng/src/main.rs:199`.
  - Consumer: `crates/harness/src/cli.rs:383-390` (`decode --mode oneshot` regrows on `output_full`, and sets `limit_hit` when `--max-output` is given).
- What is wrong:
  - Changing cf's `ERR_OUTPUT_FULL` at `subj-cf/src/main.rs:104` to another error kind survives `make test`.
  - Deleting the `avail_out == 0 => ERR_OUTPUT_FULL` arm in `zlibapi` also survives `make test`. Only `make lint` kills it, and only incidentally, through the now-unused import.
  - The harness side is tested with the fake `IdentitySubject` (`crates/harness/tests/cli.rs:41`). Every real-subject fixture, however, decompresses to less than the initial `max(4 × input, 64 KiB)` buffer, so the regrow path never runs against a real decoder.
- What would break: `decode --mode oneshot` feeds the malformed matrix (SPEC §3.6), and `--max-output` defines `limit_hit`. If a subject mislabels "buffer full", then:
  - a valid stream with ratio > 4 and output > 64 KiB would be recorded as an error (for zlib, `Z_BUF_ERROR truncated input`);
  - a limit would be reported as a decode failure.

  These are exactly the cross-subject disagreements the T3 kit highlights.
- Verified today: by hand, all seven debug binaries decode a 1 MiB zero stream in one-shot mode (zlib framing). With `--max-output 1000` on the raw stream, each reports `limit_hit: true, error_kind: output_full`. So the new tests will pass on current code.
- Fix: tests only. Add to `tests/test_rust_subjects.py` (cf, zrs, mox) and `tests/test_c_subjects.py` (zlib, zlib-nohw, zsys, zng):
  - `test_oneshot_grows_past_initial_buffer[subject]`: build 1 MiB of zeros in the test and compress it with Python `zlib` (zlib framing; raw too, since every subject supports both). Assert `decode --mode oneshot` gives `ok`, `produced == 1 MiB` and the expected sha256.
  - `test_oneshot_max_output_sets_limit_hit[subject]`: the same stream with `--max-output 1000`. Assert `ok == false`, `limit_hit == true` and `error_kind == "output_full"`.
- Task: P0-06 (cf, zrs, mox), P0-07 (zlibapi), P0-08 (zng).

### F-3 [Spec drift: R2-01 goal, SPEC §4] `framing`, `fuzz` and `fuzz-smoke` read workload streams but do not depend on `workloads`
- Where:
  - `Makefile:150` (`framing: checksums`), `:109` (`fuzz: fuzz-build`) and `:116` (`fuzz-smoke: fuzz-build`).
  - The test's needle list at `tests/test_clean_clone.py:203`.
- What is wrong: R2-01's own goal is that "every Makefile target that measures over workload streams or the cleanflate test data depends on the target that creates them". Two kinds of target still don't.
  - **`framing`.** `cfbench.framing run` is `perf.run` over the same workload streams (`cfbench/framing.py:51-55`). On a fresh clone, `make -n framing` prints `cfbench.framing run` with no `fetch` or `workloads generate` before it.
  - **`fuzz` and `fuzz-smoke`.** `cfbench.fuzzing run` seeds from the level-6 workload streams and from cleanflate's `testdata/malformed`.
    - On a fresh clone it crashes on the missing `SOURCES.json`.
    - After a bare `make fetch`, it silently seeds from the malformed files only, because `cfbench/fuzzing.py:91` skips missing streams. A 12-CPU-hour M-A run would then use a different seed corpus from M-B, with nothing flagging it.

  The R2-01 test only looks for `perf run`, `trajectory run`, `conformance run` and `content.features run`, so it cannot see either case.
- What breaks:
  - `make framing` (a SPEC §4 granular target) and `make fuzz` (manual check 2 below) do not run from a fresh clone.
  - `make fuzz` after only `make fetch` degrades silently.
  - `make all` is unaffected, because `perf` runs first.
- Fix:
  - Add `workloads` as a prerequisite of `framing`, `fuzz` and `fuzz-smoke`. `workloads` already brings in `fetch`.
  - Add `"cfbench.framing run"` and `"cfbench.fuzzing run"` to the needle list in `test_measurement_targets_depend_on_their_inputs`, and raise the `checked` floor to 9 to match.
  - The extended test fails today on `framing`, `fuzz` and `fuzz-smoke`.
- Task: R2-01.

## Mutation sample (18 mutants this round)

**Killed (14):**

| File | Mutant |
|---|---|
| `Makefile` | `trajectory` without `workloads` |
| `Makefile` | `malformed` without `fetch` |
| `Makefile` | `smoke-bench` without `workloads` |
| `cfbench/stats.py` | `like_for_like_key` without `mode` |
| `cfbench/similarity/ngram.py` | `jaccard` denominator changed |
| `cfbench/similarity/identifiers.py` | RFC exclusion dropped |
| `cfbench/unsafe_scan.py` | `unsafe extern fn` no longer counted |
| `cfbench/content/correlate.py` | `verdict` without `p < alpha` |
| `cfbench/malformed.py` | `accept+trailing` threshold changed |
| `cfbench/perf.py` | cell shuffle removed |
| `cfbench/workloads.py` | `verify` hash check removed |
| `cfbench/kits/evidence.py` | `lookup` non-unique-key guard removed |
| `crates/subj-cf/src/main.rs` | gzip mapped to the zlib format |
| `crates/harness/src/cli.rs` | `bench` output-mismatch check removed |

**Survived (4), all findings:**

| File | Mutant | Finding |
|---|---|---|
| `crates/harness/src/timing.rs` | per-iteration division removed | F-1 |
| `crates/harness/src/alloc.rs` | `dealloc` accounting removed | F-1 |
| `crates/harness/src/alloc.rs` | `realloc` accounting removed | F-1 |
| `crates/subj-cf/src/main.rs:104` | `output_full` kind changed | F-2 |

The `zlibapi` output-full arm deletion also survived `make test` (F-2); only `make lint`'s unused-import warning would catch it.

## Interpretation choices
- **R2-01:** none logged, and none needed.
- **Earlier rounds:** the choices accepted in round 2 still stand.

## Blocked and skipped tasks
None.

## Spec issues
No new ones. PLAN's Spec issues 1–13 still stand.

## Manual checks still owed (from HANDOFF.md)
1. Timing-sensitive full runs on a quiet machine, M-A and M-B: `make perf perf-native framing trajectory` (or `make paper-data` for the T1 subset), then `make content`. All their tables are pending.
2. `make fuzz` (3 targets x 4 CPU-hours) and `make bombs` (the full sweep with 4 GiB cases).
3. M-A runs of env, conformance and malformed.
4. Fill in prices in `config/pricing.toml` and the fragment verdicts in `config/similarity_verdicts.toml`.
5. Review `results/STRUCTURE_COMPARISON.md`, `RESULTS.md` (threats to validity), `PITCH_KIT/TALKING_POINTS.md` and `BLOG_NOTES.md`.
6. Run `make kits-check` after committing (it refuses a dirty tree).
7. Re-sign the commits made with `commit.gpgsign=false`, if signed history is required.
8. R2-01: run `make paper-data` from a real fresh clone (needs network). NOT VERIFIED (human).

## Notes (not findings)
- Several targets read the cleanflate clone or the C source trees without declaring `fetch` or `c-subjects`: `similarity-*`, `smoke-similarity`, `effort`, `size`. Each fails loudly with a "run `make fetch`/`make c-subjects`" message rather than degrading, and `all`, `paper-data` and `smoke` order them correctly. R2-01 put this out of scope. Adding the prerequisites would make every granular target self-sufficient, but nothing breaks today.
- `cfbench/fuzzing.py:91` skipping missing workload streams is reasonable for tests. Once F-3 lands it cannot happen through `make`.
- The round-2 notes (comparators "accept" vs `accept+trailing` wording; dead `if !inp.is_empty()` in `Cf::oneshot`; per-section parity reminders in `STRUCTURE_COMPARISON.md`) still apply.
