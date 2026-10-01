# cleanflate-bench

Head-to-head evaluation of cleanflate against zlib, zlib-ng, zlib-rs and miniz_oxide.
See `docs/SPEC.md` for the specification and run `make help` for the available targets.

## Reproducing

### Prerequisites

- Rust 1.89 through rustup (`rust-toolchain.toml` pins it), plus the `nightly` toolchain with the
  `llvm-tools-preview` component for fuzzing and coverage.
- `uv` (Python 3.12 and the locked environment), `cmake` and a C compiler.
- Java 21 or newer on the PATH (JPlag needs Java 25; a pinned Temurin JRE is downloaded when the
  installed one is older).
- ssh access to the cleanflate repository (`config/rounds.json` holds the pinned revisions).

### From a clean clone: the kits

Everything in `results/PAPER_KIT.md`, `results/PITCH_KIT/`, `results/RESULTS.md` and
`results/BLOG_NOTES.md` regenerates from the committed raw data in `data/raw/`, with no measurement:

```
uv sync --frozen
make kits          # paper, pitch and blog
make kits-check    # does the same in a fresh clone of HEAD and compares byte for byte
```

### Measurements

`make all` runs every measurement and then every kit. Some steps are human-run on a quiet machine
and are not committed from smoke runs (`data/smoke/` is ignored):

| Step | Target | Rough duration | Where |
|---|---|---|---|
| Environment, pins, workloads | `make env pins workloads` | minutes (plus downloads) | both machines |
| Performance | `make perf perf-native` | about an hour each | M-A and M-B, quiet |
| Framing and checksums | `make framing` | tens of minutes | M-A and M-B |
| Trajectory | `make trajectory` | tens of minutes | M-A and M-B |
| Conformance, malformed | `make correctness` (parts) | minutes | M-B committed; M-A to do |
| Differential fuzzing | `make fuzz` | 3 targets x 4 CPU-hours | a machine that can spare it |
| Bomb sweep | `make bombs` | minutes; 4 GiB cases | M-A and M-B |
| Size, safety, complexity | `make size` | about ten minutes (tool builds) | any |
| Similarity | `make similarity` | tens of minutes | any |
| Effort | `make effort` | minutes | where the transcripts are |

`make paper-data` runs the machine-specific T1 measurements for the machine you are on (`env`, `pins`,
`perf`, `trajectory`, `size`, `conformance`) and then renders the paper kit; `make paper` alone only renders.
It includes the timing runs, so use it on a quiet machine.

Quick profiles (`CFB_PROFILE=quick`, `make smoke`, `make fuzz-smoke`) write to `data/smoke/` and are for
checking the tooling only. Machine M-A (Apple M4) is run by a human; M-B is the Linux x86_64 workstation.
