# SPEC: cleanflate-bench — head-to-head evaluation and evidence pipeline

> Drop into `docs/SPEC.md` of a **separate** repo. Run with `/go-flight` only after `cleanflate` is merged and tagged (`v0.3.0-cleanroom`).
> Clean-room rules are **lifted** here. This repo may read comparator source and use comparator tooling. It must **never modify cleanflate**. Consume cleanflate read-only, by tag and git SHA.

## 1. Purpose and audiences

Produce reproducible, citation-ready evidence that an AI-assisted, spec-driven pipeline (Foundry) clean-room reimplemented a widely deployed C component (zlib inflate) in safe Rust. The evidence must cover verifiable provenance, correctness and performance, and compare the result honestly against the status quo.

The same data feeds three outputs of very different sizes. Every deliverable is tiered:

| Tier | Consumer | Size | Needs |
|---|---|---|---|
| **T1 Paper** | xTech|Search 10 three-page white paper (due Oct 19, 2026) | ~5 headline numbers, 1 table, 1 figure | Bulletproof, conservative, every number traceable |
| **T2 Pitch** | Virtual pitch (Jan 2027) and finals demo (Mar 2027), if advanced | 8–12 slide-ready figures and talking points | Visual, comparative, tells the improvement story |
| **T3 Blog** | Long-form technical post (published either way) | Full narrative, per-file detail, methodology, surprises | Depth, honesty, interesting findings |

**Run T1-critical milestones first** (§7). T2/T3 work must never block T1.

Every number in any tier must trace to a script in this repo, a raw data file, and a recorded environment.

## 2. Subjects

### 2.1 Primary subjects

| ID | Implementation | Language | How built |
|---|---|---|---|
| `cf` | cleanflate @ tag `v0.3.0-cleanroom` (pinned SHA) | Rust, `forbid(unsafe)` | git dependency pinned by SHA |
| `zlib` | zlib 1.3.x, **stock source build** (pinned release) | C | built from source in this repo with documented flags |
| `zng` | zlib-ng, pinned release, **native API** | C | built from source, documented flags |
| `zrs` | zlib-rs, pinned release | Rust (uses `unsafe`) | crate, pinned |
| `mox` | miniz_oxide, pinned release | Rust | crate, pinned |

### 2.2 Secondary subject
| `zsys` | Platform system zlib (Apple libz on macOS, distro zlib on Linux) | C | linked as installed. Record the exact version and build provenance where discoverable |

### 2.3 Build-provenance requirements (critical)
- For each C build, record the compiler, version, flags, and **whether hardware CRC32 is enabled**. On aarch64, that means whether ARMv8 CRC32 instructions are compiled in. On x86_64, it means whether PCLMUL/SSE4.2 paths are enabled where the implementation supports them. Determine this from build configuration and, where possible, by disassembly or symbol inspection. Write the result to `subjects.lock.json`.
- Build `zlib` twice where feasible: once with platform defaults, and once with hardware CRC explicitly **disabled**. The second build is the control that tests the hypothesis that cf's gzip gap is mostly hardware CRC (§3.3).
- **Rust profile, applied identically to cf, zrs and mox:** `opt-level=3`, `lto="fat"`, `codegen-units=1`, `panic` default. Primary runs use the generic target CPU. Run a secondary set with `-C target-cpu=native` for all Rust subjects and label it clearly.
- Record each Rust subject's `unsafe` status from inspection (§3.4). Do not assume it.

Pin everything in `subjects.lock.json`: name, version, git SHA or crate checksum, build flags, compiler, and the hardware-CRC determination.

### 2.4 Feature-parity note (must accompany every comparison table and figure)
cf implements decompression only, with no SIMD, no `unsafe` and no C ABI. Comparators implement compression, and some have SIMD paths, hardware CRC and ABI compatibility. No figure may imply apples-to-apples where it isn't.

## 3. Measurements

### 3.1 Machines
- **M-A:** Apple M4 MacBook (aarch64, macOS).
- **M-B:** Linux x86_64 workstation.
- Capture the environment on every run into `environment.json`:
  - CPU model: `sysctl -n machdep.cpu.brand_string` / `lscpu`
  - core counts
  - OS and version: `sw_vers` / `/etc/os-release`
  - kernel
  - power state (on AC; low-power mode off; `pmset -g` on macOS)
  - governor (Linux)
  - load average at start and end
  - toolchain versions
  - SHAs of both repos
- Laptop hygiene for M-A: on AC power, lid open, no other heavy processes. Record thermal state at start and end if available.

### 3.2 Performance
- **Harness:** criterion (or an equivalent with the same rigor) with warm-up, ≥30 samples per cell, and the median plus 95% CI reported. Single thread. **Randomize the order of benchmark cells** to avoid systematic thermal and turbo bias. Re-run the full suite twice per machine. Results must agree within ±5% median, or be flagged.
- **Workloads:** every Silesia and Canterbury file, compressed by stock `zlib` at levels 1, 6 and 9, in raw, zlib and gzip framing. Measure:
  - one-shot decompression
  - streaming with small buffers (1 KiB in / 4 KiB out) and large buffers (1 MiB)
  - **like-for-like:** every subject in both one-shot and streaming modes where its API allows. Never compare cf streaming against a comparator's one-shot.
  - tiny inputs (≤1 KiB) for setup cost
- **Metrics:** MiB/s of decompressed output (median and best), ns/byte, peak heap (counting allocator in-harness), and ratio vs. `zlib` (= 1.00×).
- **Aggregates:** total bytes divided by summed per-file time, per corpus. **Also report per-file results.** Aggregates can hide content effects.

### 3.3 Framing-cost decomposition (explains the gzip gap)
- **Checksum microbenchmarks** (GiB/s) for Adler-32 and CRC-32 in every subject that exposes them, plus the hardware-CRC-disabled zlib build. Buffer sizes: 64 B, 4 KiB, 64 KiB, 1 MiB.
- **Framing overhead per subject:**
  - `(1/throughput_gzip − 1/throughput_raw) / (1/throughput_raw)`
  - and the same for zlib framing.
- **Headline test:** does cf's gzip penalty roughly match stock zlib's penalty *with hardware CRC disabled*? Report the result either way. This is a T1/T2 claim candidate only if the data supports it.

### 3.4 Content analysis (explains Canterbury and level-1 behavior)
- Use **infgen** (Mark Adler's DEFLATE stream disassembler; permitted here because the clean room is lifted) or an equivalent tool to extract per-file token statistics from each compressed test stream:
  - literal fraction
  - match length histogram
  - match distance histogram (especially distance 1 and distances 2–7)
  - block type counts
  - compression ratio
- **Correlate** cf's per-file ratio vs. zlib against these features. Test these hypotheses explicitly and report the outcomes:
  - (H1) cf's relative weakness on Canterbury tracks short-distance and overlapping match density (e.g. kennedy.xls, ptt5).
  - (H2) cf's level-1 weakness tracks literal fraction.
- Output: a scatter plot of per-file ratio against each feature, with a short findings note.

### 3.5 Improvement trajectory (Foundry iterates)
- Benchmark each cleanflate round on **both machines, same harness, same session**:
  - round 1 (initial build)
  - round 2 (first perf pass / `main` before phase 3)
  - round 3 (`v0.3.0-cleanroom`)
- Take the SHAs from config (`rounds.json`).
- Report the per-round aggregate for each corpus and framing, plus the per-round wall-clock and cost from §3.8.
- Produce a figure: throughput ratio vs. zlib by round, one line per corpus × framing.

### 3.6 Correctness
- **Conformance:** every subject over the shared corpus (`cleanflate/testdata/generated` + corpora). Report the pass rate and any disagreements.
- **Malformed-input behavior matrix:** every file in `testdata/malformed/` × every subject, recording error vs. accept and bytes produced. Highlight disagreements between subjects. These are likely T3 findings.
- **Differential fuzzing:** cargo-fuzz harnesses cf↔zlib, cf↔zrs, cf↔mox, with a fixed budget (default 4 CPU-hours each, configurable). Report execution counts, coverage, divergences and triage.
- **Robustness:** decompression-bomb sweep (ratios up to ≥1:1,000,000). Measure peak RSS, time to reject, and whether each subject enforces limits natively or needs caller logic.

### 3.7 Size, safety and complexity
- **Binary size:** a minimal stdin→stdout decompress program per subject, built release + LTO + strip at `opt-level` 3 and `s`. Include `cargo bloat` for the Rust subjects.
- **Source size:** `tokei` LOC for the decompression path only, with the separation method documented.
- **`unsafe` surface:** `cargo geiger` plus grep-based block counts for cf, zrs and mox. For C subjects, note that the whole codebase is memory-unsafe by language.
- **Dependencies:** `cargo tree` (direct and transitive) and `cargo audit`.
- **Complexity:** per-function cyclomatic and cognitive complexity (`rust-code-analysis-cli` for Rust, `lizard` for C), reported as distributions (median, p90, max).

### 3.8 Clean-room verification (contamination check)
Model training data can't be controlled, so measure resemblance directly, with **both negative and positive controls**:

- **Negative control (independent implementations):** zrs ↔ mox. These are two human-written Rust implementations of the same spec with no shared lineage. This shows what "same spec, independently written" similarity looks like.
- **Positive control (known derivation):** zrs ↔ zng. zlib-rs documents that it is based on zlib and zlib-ng. This shows what derivation looks like. It's cross-language, so emphasize identifier, constant-naming and structural overlap here.
- **Test:** cf ↔ zrs, cf ↔ mox, cf ↔ zlib, cf ↔ zng.
- **Methods:**
  - Token-based clone detection (JPlag and/or Dolos). **Verify Rust support in the installed version first**, and record tool and version. Fallback: tree-sitter token n-gram Jaccard (normalized 5–10-grams, identifiers abstracted), documented.
  - Identifier overlap: exact-match rate of non-trivial identifiers (length ≥ 6), **excluding RFC-mandated names** (HLIT, HDIST, HCLEN, BFINAL, BTYPE, LEN, NLEN, and similar). Publish the exclusion list.
  - Comment n-gram overlap.
  - Structural comparison write-up covering bit reader, Huffman table strategy, window management, fast-loop design and state machine shape.
- **Top-20 fragment pairs** per test pair for human review, with a verdict column: RFC-forced / idiomatic-inevitable / suspicious.
- **Result statement:** where cf's scores fall relative to the negative and positive controls. A T1 claim is allowed only if cf sits at or near the negative control.

### 3.9 Effort, cost and provenance
- Parse, for every round:
  - `cleanflate/provenance/tool-log.jsonl`
  - git history (`[stage:…] [task:…]` tags)
  - Foundry and Claude Code usage exports
- **Report:**
  - wall-clock per milestone, stage and round
  - model per stage
  - tokens and API cost per stage, round and total. If any source is missing, document the gap and the estimation method.
  - review rounds per milestone
  - defect discovery source (review / unit tests / conformance / fuzzing)
  - human interventions (count, time, nature)
  - denied tool calls (count and categories)
- **Status-quo context (zlib-rs):** from the public GitHub API, collect first-commit date, key release dates (first release, stable-API release), contributor count and commit count. Present this as **context, not head-to-head**, and state the scope difference explicitly (full API/ABI, compression, SIMD, performance parity).

## 4. Reproducibility
- `make all` runs everything end to end. Granular targets:
  - `make env pins perf framing content trajectory correctness size similarity effort`
  - `make paper` (T1 only, fastest path)
  - `make pitch`
  - `make blog`
- Raw outputs go to `data/raw/<category>/<machine>/<timestamp>.json`, and derived tables to `results/*.csv`.
- Deterministic seeds. Fuzz corpora are archived. Charts are rendered as SVG plus 2× PNG.

## 5. Deliverables

### T1: `results/PAPER_KIT.md` (paper-critical, small)
- **5–7 headline claims**, each one sentence, conservative, with the exact supporting number, source file and script. Candidates (include only if supported):
  - conformance: "byte-identical output across N streams"
  - safety: "zero `unsafe`, zero runtime dependencies"
  - performance range vs. C zlib on Silesia (raw/zlib, levels 6–9), both machines
  - improvement trajectory across rounds
  - similarity at or near the independent-implementation baseline
  - build effort and cost
- **One table** (≤ 6 rows) summarizing cf vs. zlib vs. mox on the key metrics, with the parity footnote.
- **One figure** sized for a three-page paper. Recommended: the trajectory chart, or a cf/mox/zlib throughput bar chart with an `unsafe`-count annotation.
- **Rejected claims:** what the data does **not** support, so the paper doesn't overreach.

### T2: `results/PITCH_KIT/`
- 8–12 slide-ready figures (SVG and PNG, 16:9-friendly):
  - trajectory
  - throughput vs. all comparators
  - framing-cost decomposition
  - similarity vs. controls
  - `unsafe` counts
  - binary size
  - effort/cost per stage
  - malformed-input matrix highlights
  - fuzz stats
- `TALKING_POINTS.md`: 2–3 bullets per figure, and anticipated reviewer questions with data-backed answers. Examples: "Why is it slower than C?", "How do you know it wasn't copied?", "What does this cost?", "Can it run air-gapped / on other models?"

### T3: `results/RESULTS.md` and `results/BLOG_NOTES.md`
- **RESULTS.md:** the full narrative of every measurement, with methodology, per-file tables, all figures, parity notes, and a **threats to validity** section covering at least:
  - training-data contamination
  - machine variance and thermal effects
  - feature-scope mismatch
  - fuzz budget limits
  - n=1 build effort
  - hardware-CRC asymmetry
- **BLOG_NOTES.md:** story beats with data callouts, the most surprising findings (e.g. malformed-input disagreements between mature libraries, content-type effects), and open questions. This is notes for a human author, **not a finished blog post**.

## 6. Rules
- Never modify cleanflate. If you find a bug in cf, record it in `results/findings.md` for the build repo. Never patch it here.
- Report unfavorable results with the same prominence as favorable ones.
- No number appears in any kit without a script and raw file behind it.
- Like-for-like comparisons only, or explicitly labeled exceptions.
- Hypotheses (§3.3, §3.4) are reported as confirmed, refuted or inconclusive. Never omit them.

## 7. Milestones (ordered for the paper deadline)

**Tier 1, paper-critical (complete first):**
- **B0 Scaffolding and pins:** repo, subject builds (§2.3, including the hardware-CRC determination), `environment.json`, make skeleton, smoke runs. *Acceptance:* all subjects build on M-A, and a smoke bench and smoke similarity run complete.
- **B1 Core performance:** §3.2 one-shot and streaming on Silesia and Canterbury, M-A then M-B. *Acceptance:* two runs per machine agree within ±5% median.
- **B2 Size and safety:** §3.7 binary size, `unsafe`, dependencies. LOC and complexity can follow later.
- **B3 Similarity with controls:** §3.8. *Acceptance:* negative- and positive-control scores computed, cf positioned between them, top-20 pairs extracted.
- **B4 Trajectory and effort:** §3.5 and §3.9. *Acceptance:* per-round table and figure, cost table with gaps documented.
- **B5 PAPER_KIT:** *Acceptance:* every claim linked to data, rejected-claims list present, and `make paper` regenerates it from a clean clone.

**Tier 2/3, pitch and blog (after the T1 kit is done):**
- **B6 Framing decomposition:** §3.3, including the hardware-CRC-disabled control.
- **B7 Content analysis:** §3.4, infgen statistics and the H1/H2 verdicts.
- **B8 Correctness depth:** §3.6, full malformed matrix, differential fuzz budget, robustness sweep.
- **B9 Complexity and remaining size metrics.**
- **B10 PITCH_KIT, RESULTS.md, BLOG_NOTES.md.** *Acceptance:* `make all` reproduces everything from a clean clone. All three kits are complete, and threats-to-validity is filled in.
