# Hand-off: initial build

All 71 tasks are done (0 blocked, 0 skipped). `make lint` and `make test` pass (356 Python tests plus the Rust tests) when git signing is available; see the signing note below.

## What exists

- Cargo workspace (harness, six Rust and C subjects, minimal-size programs), pinned C builds, 288 workload streams, orchestration for perf, framing, checksums, trajectory, conformance, malformed, fuzz and bombs.
- Derived tables in `results/*.csv` with provenance sidecars; figures in `results/figures/`.
- Kits: `results/PAPER_KIT.md`, `results/PITCH_KIT/`, `results/RESULTS.md`, `results/BLOG_NOTES.md`. `make kits-check` regenerates all of them in a fresh clone and they are byte-identical.
- Committed M-B data (deterministic, non-timing): env, pins, size, unsafe, deps, loc, complexity, similarity, effort, content features, malformed matrix, conformance (2962/2962 for cf).

## Needs a human

1. Timing-sensitive full runs on a quiet machine, M-A and M-B: `make perf perf-native framing trajectory`, then `make content`. All their tables are pending.
2. `make fuzz` (3 targets x 4 CPU-hours) and `make bombs` (4 GiB cases). A 60 s smoke run of each worked (not committed).
3. M-A runs of env, conformance and malformed.
4. Fill in prices in `config/pricing.toml` (all unset, so cost is unavailable); fragment verdicts in `config/similarity_verdicts.toml`.
5. Review `results/STRUCTURE_COMPARISON.md`, `RESULTS.md` (threats to validity), `PITCH_KIT/TALKING_POINTS.md`, `BLOG_NOTES.md`.

## Notable results so far

- The generated similarity statement says the T1 independence claim is NOT allowed: identifier metrics put cf-mox and cf-zrs between the controls. JPlag's longest cf-zrs match is structural.
- Malformed inputs: 4 of 42 files split subjects, all cf being stricter (trailing data, bad second gzip member); cf matches EXPECTED.tsv everywhere.
- cf binary is larger than zlib (385 vs 42 KiB at opt 3); cf has 0 unsafe blocks.
- Content analysis: infgen features for 207 corpus workloads; H1 and H2 pending perf data.
- Complexity and LOC tables are in `results/complexity.csv` and `results/loc.csv`.

## Interpretation choices and caveats

- Logged per task in `docs/PROGRESS.md`. Key ones: bombs are compressed with Python's streaming zlib (cfb-zlib reads the whole input); bomb RSS carries the launcher's RSS as a floor (`rss_floor_bytes`); miniz_oxide skips its Adler-32 check under `--cfg fuzzing`, so the fuzz harness verifies it itself; tokei reports Rust doc comments as embedded Markdown rows.
- Signing: the 1Password SSH agent died during P10-02. Commits after that were made with `commit.gpgsign=false` (local). With the agent down, `make test` fails only in throwaway-repo tests (clean_clone, cleanflate_src); they pass with a signing override. Re-sign if required. Friction is logged in `.foundry/feedback.jsonl`.
- No tool gaps: tokei 15.0.0, rust-code-analysis-cli 0.0.25, lizard 1.24.0, JPlag 6.3.0, infgen pinned, nightly llvm-tools-preview installed.

## Round 1

Review-fix round on branch `build/2026-10-01`. All eight R1 tasks done, none blocked; lint and 374 tests green.

- R1-01: git helpers in tests use shared `HERMETIC_GIT_ARGS` and `hermetic_git_env()` (tests/conftest.py): no dependence on user git config or signing.
- R1-02: `Subject::oneshot` returns `OneshotOutcome {produced, consumed}`; decode oneshot reports real `consumed` and `trailing_bytes`. M-B malformed matrix re-run (new raw file) and kits regenerated; zlib family, zrs and mox now show `accept+trailing` on trailing_byte.bin, cf rejects. The harness test IdentitySubject treats a NUL byte as a stream terminator to produce trailing input.
- R1-03: `md_table` appends the parity note after every table; methodology/threats text says load is a warning and refused only with `--strict`; all four chunk sizes listed.
- R1-04: `check_bullet` compares whole number tokens. Rejection bullets quoting cell tallies carry labels computed from the evidence list (len and count below parity_ratio). Paper test allows the baseline `1.00`.
- R1-05: boundary tests for `framing.hypothesis_tolerance` and the content rho thresholds; no code change.
- R1-06: binary_size figure labels unmeasured slots `n/a`; committed figure unchanged.
- R1-07: bombs table gains `overall_ratio`; `ratio` is per row. Table is still pending (full sweep is a human step).
- R1-08: `make paper-data` added (env pins perf trajectory size conformance, then paper); not run.

Human checks: run `make paper-data` on M-A and M-B; the full bomb sweep; kits-check requires a clean tree, so run it after committing.
