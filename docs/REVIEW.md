# Review: build/2026-10-01
Round: 2

**Verdict: CHANGES REQUESTED**

Scope: the whole branch `e17e6973d7a7..edc8dd1`. Round 1 reviewed every original task commit. This round re-checks the branch with the eight R1 fix commits (`085bc3d`..`15c3bd4`, plus `bef03e6`, which regenerated the kits). For each one I read the diff, then the R1 task in PLAN, then the SPEC sections it cites.

Verify result:
- `foundry_verify`: all 10 mechanical constraints pass, with no fixture failures and no hits. `make lint` is green, and `make test` is green (374 Python tests plus the Rust tests).
- The signing agent is still unavailable in this environment, and the throwaway-repo tests now pass anyway.
- `make kits-check` on the clean tree reports every kit file identical.

## Round-1 findings: status

| R1 finding | Status | Evidence |
|---|---|---|
| F-1 (hermetic git) | Fixed | Mutant removing both isolation layers in `tests/conftest.py` is killed (6 failed, 4 errors). |
| F-2 (oneshot consumed/trailing) | Fixed | `decode --mode oneshot` reports `consumed` and `trailing_bytes` from each subject. New raw file `data/raw/correctness/M-B/20261001T073606Z.json` added; old raw files untouched. The matrix now shows 22 `accept+trailing` cells, and all four disagreements are cf stricter. Mutants killed: zlibapi stream `trailing_bytes: 0`, zng oneshot `consumed: input.len()`, cli.rs trailing assignment deleted, cf `TrailingData::Allow`. |
| F-3 (parity note, methodology text) | Fixed | All 21 RESULTS.md tables carry the note. Load-precondition and chunk-size wording now matches the code. Mutant removing the note from `md_table` is killed. |
| F-4 (substring evidence) | Fixed | Mutants restoring the substring clause and corrupting the computed tallies are both killed. `blog.py` uses the same `check_bullet`. |
| F-5 (threshold boundaries) | Fixed | Mutants `1.5 * tol` and "drop `min_abs_rho`" are both killed. |
| F-6 (binary-size n/a) | Fixed | Mutant restoring `d.get(opt, 0)` is killed. |
| F-7 (bomb per-layer ratio) | Fixed | Mutant restoring the overall ratio in `ratio` is killed. |
| F-8 (`make paper-data`) | Partly fixed | The target exists and its prerequisite list is tested (mutant dropping `conformance` is killed). It cannot run from a fresh clone; see F-1 below. |

## Findings (most severe first)

### F-1 [Spec drift: SPEC §4, B10 acceptance, PLAN Decisions] `make all` and `make paper-data` run perf before any workload stream exists, so both fail on a fresh clone
- Where:
  - `Makefile:75` (`perf: subjects`), `:79` (`perf-native: subjects subjects-native`), `:91` (`trajectory: subjects subjects-rounds`), `:171` (`smoke-bench: subjects`) and `:123` (`malformed: subjects`).
  - `paper-data` and `all` list these targets ahead of anything that builds `workloads` or runs `fetch`.
  - Consumers: `cfbench/perf.py:145-148` and `cfbench/trajectory.py:90`.
- What is wrong:
  - `data/workloads/` and `third_party/` are gitignored, so a fresh clone has neither the cleanflate clone nor the workload streams.
  - `perf run` calls `workloads.list_workloads` (which needs the cleanflate corpora via `cleanflate_src.corpus_files`) and raises `RuntimeError("... workload streams are missing: run make workloads")`.
  - `make -n paper-data` prints `cfbench.perf run` at line 5, but `cleanflate_src fetch` only at line 25 and `cfbench.workloads generate` at line 27. Both come in later, through `conformance`.
  - `make -n all` has the same order (perf run at line 5, workloads generate at line 26). There, `perf-native` also runs before `content-features` brings in `workloads`.
  - In `paper-data`, `trajectory` also precedes `conformance`.
  - `malformed` reads `third_party/cleanflate/testdata/malformed`, but it does not depend on `fetch`.
- What breaks: SPEC §4 says "`make all` runs everything end to end", and B10's acceptance requires it to reproduce everything from a clean clone. The human step this round added (run `make paper-data` on M-A from a fresh clone) stops at its first measurement. The same applies to `make all` and `make smoke`, which B0's acceptance names. `make kits-check` only re-renders kits, so nothing has exercised the measuring chain from a fresh clone.
- Fix:
  - Add `workloads` as a prerequisite of `perf`, `perf-native`, `smoke-bench` and `trajectory`. `workloads` already depends on `fetch subjects`.
  - Add `fetch` as a prerequisite of `malformed`.
  - Keep the Makefile GNU make 3.81 portable.
- Test: one Makefile-structure test in `tests/test_clean_clone.py`, which already parses the Makefile:
  - For every target whose recipe runs `cfbench.perf run`, `cfbench.trajectory run`, `cfbench.conformance run` or `cfbench.content.features run`, `workloads` must be a transitive prerequisite.
  - For `malformed`, `fetch` must be one.
  - In `make -n all` and `make -n paper-data`, the first `cfbench.workloads generate` must come before the first `cfbench.perf run` and `cfbench.trajectory run`.
  - It fails today.
- Task: P10-06 (`make all`) and R1-08 (`paper-data`).

## Mutation sample (14 mutants this round)
- **Killed (13):**
  - `zlibapi` stream `trailing_bytes`
  - `subj-zng` oneshot `consumed`
  - `harness/cli.rs` oneshot trailing assignment
  - `subj-cf` `TrailingData::Allow`
  - `results_md.md_table` parity note
  - `pitch.check_bullet` substring clause
  - `pitch.bullets_claims` tallies
  - `framing` tolerance band (`1.5 * tol`)
  - `correlate` `min_abs_rho`
  - `bombs` per-layer `ratio`
  - `more_charts.binary_size` zero bar
  - `Makefile` `paper-data` prerequisites
  - `tests/conftest.py` hermetic isolation
- **Survived (1, equivalent):** deleting the `if !inp.is_empty()` block at the end of `Cf::oneshot` (`crates/subj-cf/src/main.rs:114-117`). It is unreachable: cleanflate's `decompress` already returns `TrailingData` in the call that reaches `Done` with leftover input (cleanflate `85f2100` `crates/cleanflate/src/stream.rs:364-373`). The behaviour it was meant to guard is covered: `test_trailing_byte_reported[cf]` kills the `TrailingData::Allow` mutant. Not a finding.

## Interpretation choices (HANDOFF round 1)
- **R1-01, helper-level isolation instead of an autouse fixture:** accepted. PLAN allowed either approach, and both layers (`-c` flags and env) are in place.
- **R1-02, `IdentitySubject` treats NUL as a stream terminator:** accepted. It is a test-only stand-in in `crates/harness/tests/`, which is where literal values belong.
- **R1-04, tally labels computed from the evidence list:** accepted. The labels are derived from the same `Evidence` objects, not typed in, and a mismatch still raises.
- **R1-04, paper test allows the baseline `1.00`:** accepted. It is the definitional zlib = 1.00x baseline from SPEC §3.2.
- **R1-07, `overall_ratio` empty for single-layer rows:** accepted. This matches the task.
- **R1-08, `paper-data` not run:** accepted as a human step. The ordering defect is F-1.

## Blocked and skipped tasks
None.

## Spec issues
No new ones. PLAN's Spec issues 1–13 still stand.

## Manual checks still owed (from HANDOFF.md)
1. Timing-sensitive full runs on a quiet machine, M-A and M-B: `make perf perf-native framing trajectory` (or `make paper-data` for the T1 subset, once F-1 is fixed), then `make content`. All their tables are pending.
2. `make fuzz` (3 targets x 4 CPU-hours) and `make bombs` (the full sweep with 4 GiB cases).
3. M-A runs of env, conformance and malformed.
4. Fill in prices in `config/pricing.toml`, and fragment verdicts in `config/similarity_verdicts.toml`.
5. Review `results/STRUCTURE_COMPARISON.md`, `RESULTS.md` (threats to validity), `PITCH_KIT/TALKING_POINTS.md` and `BLOG_NOTES.md`.
6. Run `make kits-check` after committing (it refuses a dirty tree).
7. Re-sign commits made with `commit.gpgsign=false`, if signed history is required.

## Notes (not findings)
- BLOG_NOTES.md (lines 26-27) and TALKING_POINTS.md (lines 49-50) still say comparators "accept it". The matrix now shows `accept+trailing`, meaning they return success and leave the trailing input unconsumed. Saying that outright would sharpen the T3 story. This is human-review material (manual check 5); the sentences are not false.
- `Cf::oneshot`'s final `if !inp.is_empty()` block is dead code given cleanflate's behaviour (see the mutation sample). It is harmless as a defensive check.
- `STRUCTURE_COMPARISON.md` has 6 hand-written tables with a single parity paragraph at the top. That is acceptable for a non-numeric write-up, but a per-section reminder would match the RESULTS.md convention.
