# Decompression-path separation

Source-size (SPEC 3.7) and similarity (SPEC 3.8) measurements both need "the decompression path only".
`config/decomp_paths.toml` is the single manifest; `cfbench.decomp_paths.files(subject)` resolves it
against the pinned sources. Any include glob that matches nothing raises `StaleManifest`, so a version
bump that moves files cannot silently shrink a measurement. List a subject's files with
`python -m cfbench.decomp_paths list <cf|zlib|zng|zrs|mox>`.

## Inclusion rule

Include the code reachable from the decompress entry point, plus checksums and shared utilities that the
decompressor calls. Exclude:

- everything on the compression side (deflate, trees, match finders, slide-hash, insert-string, compare256);
- the gz file API (`gz*.c`) and the callback API (`infback.c`);
- C-ABI wrapper crates (libz-rs-sys);
- tests, benches, examples and test hooks;
- crate roots that only declare modules or shared enums for both directions (`lib.rs`).

The clean room is lifted for this repo (SPEC header), so reading comparator source to make these
decisions is permitted.

## SIMD and arch files

zlib-ng keeps its SIMD code under `arch/<isa>/`. The files implementing adler32, crc32, chunkset (the
copy primitive used by the inflate fast loop) and the per-ISA feature detection and dispatch headers are
included for every ISA, not only the one a given machine builds. Counting all ISAs makes the zng number
a property of the source tree rather than of one build; the build-specific view is in `subjects.lock.json`
and the binary-size tables. `compare256_*` and `slide_hash_*` are deflate-only and excluded.
zlib-rs puts its SIMD under `src/adler32/` and `src/crc32/`, which are included whole, together with
`src/cpu_features.rs`.

## Per-subject decisions

| Subject | Included | Notable decisions |
|---|---|---|
| cf | `src/**/*.rs` | Decompression only, so everything is on the path. `src/tests/` and `src/test_hooks.rs` are excluded. `stats.rs` (feature-gated counters) stays in. |
| zlib | `inflate.c/.h`, `inffast.c/.h`, `inftrees.c/.h`, `inffixed.h`, `adler32.c`, `crc32.c/.h`, `uncompr.c`, `zutil.c/.h` | `zutil.c` and `adler32.c` are shared with deflate but are needed by inflate, so they count in full. `zconf.h` and `zlib.h` (public declarations) are excluded. |
| zng | `inflate*`, `inffast_tpl.h`, `inftrees.*`, `inffixed_tbl.h`, `adler32*`, `crc32*`, `chunkset_tpl.h`, `functable.*`, `cpu_features.*`, `zutil*`, `uncompr.c`, small utility headers, the arch files above | `functable.c` also dispatches deflate helpers; it is included because inflate cannot run without it. The `zbuild.h`, `zendian.h`, `zmemory.h`, `fallback_builtins.h` utility headers are shared with deflate and included in full. |
| zrs | `src/inflate.rs`, `src/inflate/**`, `src/adler32*`, `src/crc32*`, `src/allocate.rs`, `src/cpu_features.rs`, `src/weak_slice.rs`, `src/c_api.rs` | `c_api.rs` is not separable into types only, so the whole file (the `z_stream` ABI types, 261 lines) is counted, which slightly overstates zrs relative to cf, which has no C ABI. `libz-rs-sys` is excluded entirely. |
| mox | `src/inflate/**`, `src/shared.rs` | `lib.rs` holds the stream status and flush enums used by both directions and is excluded; `shared.rs` is the Adler-32 helper used by inflate. |

Limits: this is a file-level separation. Where a file mixes inflate and deflate code (zng `functable.c`,
zlib `zutil.c`) the whole file counts. Functions-level separation would need call-graph tooling and is
not attempted.
