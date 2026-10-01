# cleanflate-bench

Head-to-head evaluation of cleanflate (`cf`, clean-room safe-Rust inflate) against zlib, zlib-ng, zlib-rs, miniz_oxide and system zlib. Source of truth: `docs/SPEC.md`.

## Principles
- Every number in any kit traces to a script in this repo, a raw data file and a recorded environment (SPEC §1, §6).
- Report unfavourable results with the same prominence as favourable ones. Hypotheses end as confirmed, refuted or inconclusive, and are never omitted.
- Compare like for like only: the same workload, level, framing, mode and session. Never compare cf streaming against a comparator's one-shot. Label every exception.
- Every table and figure carries the §2.4 parity note (`cfbench.parity.PARITY_NOTE`).
- T1 (paper) work is never blocked by T2/T3 work. Missing data renders as "Pending", never as a guess.
- Reproducible: deterministic seeds, pinned versions, and byte-identical derived outputs on regeneration.

## Commands
- `make lint`: cargo fmt check, clippy `-D warnings`, ruff check and ruff format check.
- `make test`: `cargo test --workspace`, debug build of the bins, `uv run --frozen pytest -q`.
- `make subjects`: release build of every `cfb-<id>` binary. `make c-subjects` builds the C libraries.
- `make fetch`: pinned cleanflate clone plus corpora. `make workloads`, `make pins`, `make env`.
- `make smoke`: quick perf plus quick similarity (writes to `data/smoke/`, never committed).
- Categories (measure, then derive): `make env pins perf framing content trajectory correctness size similarity effort`.
- Kits (re-derive from committed raw, then render): `make paper`, `make pitch`, `make blog`, `make kits`. Checks: `make paper-check`, `make kits-check`.
- `make all` runs every measurement and then every kit. `make fuzz-build` builds the fuzz targets (nightly).
- Python modules run as `uv run --frozen python -m cfbench.<module> ...`. Profile: `CFB_PROFILE=quick|full` (default full). Machine: `CFB_MACHINE`.

## Module map
- `crates/harness`: `Subject` trait, CLI (`info`, `bench`, `decode`, `checksum`, `compress`), timing loop, counting allocator plus `c_zalloc`/`c_zfree`.
- `crates/subj-{cf,zrs,mox,zng,zlib,zlib-nohw,zsys}` → binaries `cfb-<id>`. `crates/zlibapi` is the shared zlib-API FFI. `crates/min-{cf,zrs,mox}` and `minimal/c/` hold the minimal programs for binary size.
- `fuzz/`: separate nightly workspace with the differential targets `diff_cf_{zlib,zrs,mox}`.
- `cfbench/`:
  - Infrastructure: `paths`, `config`, `machine`, `env`, `rawio`, `provenance`, `download`, `tools`.
  - Inputs and builds: `cleanflate_src` (pinned clone, corpora, pristine check), `cbuild`, `pins`, `sources`, `unsafe_scan`, `decomp_paths`, `subjects`, `workloads`.
  - Measurements: `perf`, `stats`, `perf_report`, `agreement`, `charts`, `parity`, `perf_charts`, `more_charts`, `size`, `deps`, `loc`, `complexity`, `trajectory`, `conformance`, `malformed`, `fuzzing`, `bombs`, `checksums`, `framing`.
  - Packages: `similarity/` (`tokens`, `ngram`, `pairs`, `identifiers`, `comments`, `jplag`, `fragments`, `summary`, `run`, `smoke`), `content/` (`infgen`, `features`, `correlate`), `effort/` (`history`, `usage`, `context`, `derive`), `kits/` (`evidence`, `claims`, `paper_assets`, `paper`, `pitch`, `results_md`, `blog`), `clean_clone`.
- `config/`: `bench.toml` (every tunable), `subjects.toml`, `rounds.json`, `tools.toml`, `decomp_paths.toml`, `pricing.toml`, `rfc_identifiers.txt`, `similarity_verdicts.toml`.
- Data: `data/raw/<category>/<machine>/<ts>.json` (committed), `data/smoke/` (ignored), `data/workloads/` (ignored, hashes in `data/manifests/workloads.json`).
- Results: `results/*.csv` plus `.provenance.json` sidecars, `results/figures/`, kits, `results/findings.md`.
- Ignored inputs: `third_party/` (cleanflate clone, downloads, sources, tools), `build/c/<id>/` (C libraries).

## Constraints
- Never modify cleanflate. Consume it by tag and SHA (`config/rounds.json`). Writes into `third_party/cleanflate` are limited to its own gitignored products (corpora fetch, `oracle generate` with `--locked`), each followed by `cleanflate_src.pristine_check()`. No git write subcommand anywhere in `cfbench/`, `scripts/` or the Makefile (rule `cleanflate-read-only-git`). A cf bug goes in `results/findings.md` and is never patched here.
- Python randomness comes only from `random.Random(seed)` or `np.random.default_rng(seed)` with the seed from config `run.seed` (rule `no-unseeded-random-py`). Rust never uses thread or OS RNGs (rule `no-unseeded-random-rs`).
- No hard-coded tunables. SPEC numeric defaults live in `config/bench.toml`, and code reads them (rule `no-hardcoded-tunables`). Rust harness tests that need literal values go in `crates/harness/tests/`, never inline `#[cfg(test)]`. `content.alpha` is outside the rule's name list, so the reviewer checks it by reading.
- Only `cfbench/rawio.py` and `cfbench/env.py` read the wall clock (rule `wall-clock-only-in-rawio-env`). Derived CSVs, figures and kits must be byte-identical on regeneration: sorted rows, `.6g` floats, and no timestamps other than those copied from raw files.
- Only `cfbench/rawio.py` spells the `data/raw` path (rule `raw-paths-only-via-rawio`). Raw files are never hand-edited.
- Figures are saved only through `charts.save_figure` (rule `figures-only-via-save-figure`), which requires `parity_note`. Kit tables carry the parity footnote. The reviewer checks tables by reading.
- Kits print numbers only through `kits.evidence.Evidence` (table → raw files → script). Reviewer checks by reading; `tests/test_paper_kit.py` enforces it for the paper.
- Like-for-like: ratios join on (machine, session, workload, level, framing, mode). Unsupported cells are `unsupported`/"n/a", never zero. Reviewer checks by reading; covered by the stats and perf_report tests.
- Single-threaded harness, subjects and minimal programs (rule `harness-single-threaded`).
- Rust release profile `opt-level=3`, `lto="fat"`, `codegen-units=1`, only in the root `Cargo.toml`. Member crates never add profiles. Enforced by `tests/test_pins.py::test_rust_profile_matches_cargo_toml`.
- Every subject verifies checksums with its default options. No "skip checksum" flags. Reviewer checks by reading.
- Shell and Makefile stay portable to macOS (bash 3.2, BSD tools, GNU make 3.81) (rule `portable-shell-and-make`). Prefer Python over shell.
- Tests are hermetic: no network, only recorded fixtures (rule `hermetic-tests`).
- Every download is pinned by URL and SHA-256 in `config/`. Every tool is pinned by version in `config/tools.toml`.

## Task protocols
- **Data-run protocol.** When a task says to commit a data run, run the stated `make`/module command on this machine (M-B) with the full profile, and commit the new `data/raw/...` files together with the regenerated `results/` files in the task's commit. Never edit raw files. If the run exceeds the foreground limit, run it as a background shell (timeout ≤ 60 min) and wait. If it still cannot finish, log `Data run: NOT RUN (<reason>)` in `docs/PROGRESS.md` and add it to the phase-end manual check.
- **Smoke-only protocol.** For timing-sensitive categories (perf, perf-native, checksums, framing, trajectory, fuzz budget, bombs), the implementer runs only `CFB_PROFILE=quick`, which writes to `data/smoke/`. Never commit smoke data. Full runs are human, on a quiet machine.
- **Pinned-download protocol.** Download through `cfbench.download.fetch`. If the SHA-256 in config is empty, fetch once, record the computed hash in config, and state "pinned at task time: <hash>" in the commit Interpretation. A later mismatch is a blocker; never update the hash silently.
- **Tool-gap protocol.** If a third-party tool cannot be installed or run (cargo-geiger, JPlag Rust support, rust-code-analysis-cli, cargo-audit's advisory DB), record `{tool, version, command, error}` in the raw payload's `tool_gaps`, use the documented fallback, mark the affected numbers unavailable, and continue. A tool gap never blocks the task.
- **Pending-data protocol.** A derivation or kit with missing inputs still exits 0 and writes explicit `pending` (sidecar `pending` field, or a "Pending: run `make X` on M-Y" line). It never writes a placeholder number.
- **Hypothesis protocol.** Verdicts are `confirmed`, `refuted` or `inconclusive`, decided by the config thresholds named in the task, and always printed with n, the statistic and its p-value or band.
- **Phase-end protocol.** Make no code changes. Run `git push -u origin HEAD`. Append a progress-log entry containing the task's checklist verbatim and the line `Manual check: NOT VERIFIED (human)`, mark the task done, and move on. No later task waits on it.

## Commit template
```
<ID>: <title>

Goal: <one sentence>
Tests: <test files/names added or run; verify commands>
Interpretation: <choices made where SPEC/PLAN allowed more than one reading; pinned hashes; fallbacks>
Measurement: n/a (or: data-run command, raw file paths)
Manual check: none (or: NOT VERIFIED (human): <what>)
```

SPEC.md wins over PLAN.md, and PLAN.md wins over code comments.
