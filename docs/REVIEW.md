# Review: build/2026-10-01
Round: 4

**Verdict: APPROVED**

Scope: the whole branch `e17e6973d7a7..dde7837` (83 tasks, all done, none blocked or skipped). Rounds 1 to 3 reviewed every original task commit and every R1 and R2 fix. This round:
- reviews R3-01 (`0ea60b6`), R3-02 (`ca03e04`) and R3-03 (`c300354`) against their PLAN entries and SPEC §3.2, §3.6 and §4;
- re-runs, through `foundry_mutate`, every mutant the R3 tasks name. The implementer could only check them by hand.
- widens the mutation sample to modules no earlier round mutated: `framing`, `bombs`, `stats.best`, `complexity`, `effort.derive`, and the zrs and zng subjects.

Verify result:
- `foundry_verify`: all 10 mechanical constraints pass, with no fixture failures and no hits.
- `make lint` is green. `make test` is green (389 Python tests plus the Rust tests).

## Round 3 fix status

| Task | Status | Evidence |
|---|---|---|
| R3-01 (timing per-iteration, alloc free/realloc) | Fixed | Three mutants are killed by `make test`. Dropping `/ iters as f64` fails `samples_are_per_iteration` (sum × iters exceeds total elapsed). Deleting `sub` in `dealloc` fails `dealloc_and_realloc_are_counted` ("after 67118544") and `peak_tracks_largest_live_allocation`. Deleting `sub` in `realloc` fails `dealloc_and_realloc_are_counted` ("grown 100672493") and `c_zalloc_round_trip_is_counted`. The new timing assertion is a load invariant: it held in about 2,000 runs, including 800 under 8-way CPU overload. |
| R3-02 (one-shot output-full) | Fixed | Five mutants are killed: the cf `ERR_OUTPUT_FULL` kind changed; the `zlibapi` `avail_out == 0` arm disabled; the mox `HasMoreOutput` kind changed; the zrs arm disabled; the zng arm disabled. Each was run with `make test` only. Each fails both new tests for the affected subjects. |
| R3-03 (framing, fuzz and fuzz-smoke depend on workloads) | Fixed | `make -n framing`, `make -n fuzz` and `make -n fuzz-smoke` all print `cleanflate_src fetch`, then `workloads generate`, before the run. Two mutants are killed by `test_measurement_targets_depend_on_their_inputs`: dropping `workloads` from `framing`, and dropping it from `fuzz-smoke`. |

## Findings (most severe first)

None.

Checks this round turned up nothing in categories 1 to 7:
- **Constraints:** the R3 diffs are tests and Makefile prerequisites only.
  - No literals were added outside `crates/harness/tests/`.
  - No threads, network, or git write subcommands were added.
  - The Makefile lines stay 3.81-portable.
- **Boundaries:** none crossed. No edits to `.gitignore`, editor config or CI config in this round.
- **Tests:** see the table above and the mutation sample below. Every sampled mutant was killed.
- **Spec drift:** none.
  - R3-03 also edited `crates/harness/tests/alloc.rs`, which is outside its file list. It loosened the lower bound of R3-01's new alloc test to `BIG - SLACK` after one flake. The commit's Interpretation line logs it, the change is tests only, and the realloc mutant is still killed (1.5 × BIG lies far above the `BIG + SLACK` bound). I accept it.

## Mutation sample (15 mutants this round, all killed)

| File | Mutant | Killed by |
|---|---|---|
| `crates/harness/src/timing.rs` | per-iteration division removed | `timing::samples_are_per_iteration` |
| `crates/harness/src/alloc.rs` | `dealloc` decrement removed | `alloc::dealloc_and_realloc_are_counted` and one more alloc test |
| `crates/harness/src/alloc.rs` | `realloc` decrement removed | `alloc::dealloc_and_realloc_are_counted` and one more alloc test |
| `crates/subj-cf/src/main.rs` | output-full kind changed to `data_error` | `test_oneshot_*[cf]` |
| `crates/zlibapi/src/lib.rs` | `avail_out == 0` arm disabled | `test_oneshot_*[zlib, zlib-nohw, zsys]` |
| `crates/subj-mox/src/main.rs` | `HasMoreOutput` kind changed | `test_oneshot_*[mox]` |
| `crates/subj-zrs/src/main.rs` | output-full arm disabled | `test_oneshot_*[zrs]` |
| `crates/subj-zng/src/main.rs` | output-full arm disabled | `test_oneshot_*[zng]` |
| `Makefile` | `framing` without `workloads` | `test_measurement_targets_depend_on_their_inputs` |
| `Makefile` | `fuzz-smoke` without `workloads` | `test_measurement_targets_depend_on_their_inputs` |
| `cfbench/framing.py` | overhead denominator changed to the framed rate | `test_overhead_formula` and the hypothesis test |
| `cfbench/bombs.py` | Linux `ru_maxrss` KiB conversion removed | `test_ru_maxrss_normalized_per_platform` |
| `cfbench/stats.py` | `best` takes the maximum | `test_median_even_and_odd` and the `cell_stats` test |
| `cfbench/complexity.py` | p90 rank off by one | `test_distribution_nearest_rank_p90` |
| `cfbench/effort/derive.py` | null cost no longer propagates | `test_null_cost_propagates_and_is_listed_in_gaps` |

The zlibapi mutant counts once, although it covers three subjects. Every module touched in round 3 was mutated at least once, and so was every crate the R3 tests cover.

## Interpretation choices
- **R3-01:** the alloc lower bound was later loosened to `BIG - SLACK` (in R3-03). Accepted, as described above.
- **R3-02:** the tests use zlib framing only, while PLAN's design constraint mentions "zlib and raw framing". Accepted:
  - the acceptance-test text describes a single stream;
  - the output-full arm in every subject is framing-independent (framing only changes header and checksum flags);
  - every named mutant is killed.
- **R3-03:** the `alloc.rs` scope addition. Accepted, as described above.
- **Earlier rounds:** the choices accepted in rounds 1 to 3 still stand.

## Blocked and skipped tasks
None.

## Spec issues
No new ones. PLAN's Spec issues 1–13 still stand. Two of them visibly shape the current results:
- Issue 6: the x86_64 hardware-CRC control is identical to the default build.
- Issue 7: the positive control is cross-language.

## Manual checks still owed (from HANDOFF.md)
1. Timing-sensitive full runs on a quiet machine, M-A and M-B: `make perf perf-native framing trajectory` (or `make paper-data` for the T1 subset), then `make content`. All their tables are pending.
2. `make fuzz` (3 targets x 4 CPU-hours) and `make bombs` (the full sweep with 4 GiB cases).
3. M-A runs of env, conformance and malformed (and `make fetch c-subjects subjects pins` for the M-A `subjects.lock.json` entry).
4. Fill in prices in `config/pricing.toml` and the fragment verdicts in `config/similarity_verdicts.toml`.
5. Review `results/STRUCTURE_COMPARISON.md`, `RESULTS.md` (threats to validity), `PITCH_KIT/TALKING_POINTS.md` and `BLOG_NOTES.md`.
6. Run `make kits-check` after committing (it refuses a dirty tree).
7. Re-sign the commits made with `commit.gpgsign=false`, if signed history is required.
8. R2-01 and R3-03: run `make paper-data`, `make framing` and `make fuzz` from a real fresh clone (needs network). NOT VERIFIED (human).

## Notes (not findings)
- **Pre-existing timing-test flake (P0-05), load-sensitive.** `crates/harness/tests/timing.rs:12-29` (`calibrates_iterations_to_min_sample_time`) asserts that every sample lasts at least `0.5 × min_sample_ms`.
  - The code does not guarantee this. If the thread is preempted during one calibration pass, `measure` legitimately picks a smaller `iters`, and the later, unpreempted samples are short (observed: 0.4–1.6 ms against a 2.5 ms floor).
  - Measured failure rates:
    - with `cargo test` alone: 1 failure in about 240 runs;
    - under 3-way concurrent load: 1 in about 600 binary runs;
    - under 8-way overload on 8 cores: about 10 in 800.
  - The test is in the `make test` gate, so a rare red can appear when the machine is busy. A follow-up could keep the `iters > 1` and per-iteration (`s >= 90 µs`) assertions, which are load invariants, and drop or loosen the per-sample floor. Calibration would then still be covered by the round-1 mutant check.
  - This is not a finding: the round-1 calibration mutant is still killed, and the defect is in the test, not in the measurement.
- The round-3 notes still apply:
  - granular `similarity-*`, `effort` and `size` targets fail loudly without `fetch` or `c-subjects`;
  - `cfbench/fuzzing.py:91` skips missing streams, which `make` can no longer trigger.
- The round-2 notes still apply: comparators "accept" vs `accept+trailing` wording; the dead `if !inp.is_empty()` in `Cf::oneshot`; per-section parity reminders in `STRUCTURE_COMPARISON.md`.
