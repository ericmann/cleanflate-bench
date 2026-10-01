# Differential fuzz targets

`fuzz/` is its own Cargo workspace (excluded from the root) and builds on the nightly toolchain.

| Target | Compares cf against | Framings |
| --- | --- | --- |
| `diff_cf_zlib` | zlib 1.3.2, from `build/c/zlib/lib/libcfbz_default.a` | raw, zlib, gzip (first byte mod 3) |
| `diff_cf_zrs` | libz-rs-sys `=0.6.8` | raw, zlib, gzip (first byte mod 3) |
| `diff_cf_mox` | miniz_oxide `=0.9.1` | raw, zlib (first byte mod 2) |

cleanflate is pinned to the revision `subj-cf` round 3 uses (`config/rounds.json`). The first input
byte selects the framing; the remaining bytes are the compressed stream.

## Commands

```
make fuzz-build                                         # fmt check, unit tests, cargo +nightly fuzz build
cd fuzz && cargo +nightly test                          # the normalization tests
cd fuzz && cargo +nightly fuzz run diff_cf_zlib         # one target by hand
```

`make fuzz` and `make fuzz-smoke` (budgeted runs and corpus archive) come from `cfbench.fuzzing`.

## Normalizations (all live in `src/lib.rs`)

Each side decodes with a 64 MiB output cap. The harness compares only accept versus reject and the
output bytes; a divergence panics with a message that names both outcomes, so libFuzzer saves the
artifact.

1. **Trailing data.** cf runs with `TrailingData::Allow`; the references stop at the end of the
   first stream. Bytes after the logical end never count as a difference.
2. **gzip members.** cf decodes every concatenated member, while one zlib `inflate` call stops
   after the first. The zlib-family references therefore reset and continue while the remaining
   input starts with `1f 8b`. A bad second member is then a real divergence, not an API artifact.
3. **Output cap.** Both sides exceeding the cap counts as agreement. One side capped and the other
   accepting is a divergence (so a stream of exactly 64 MiB can raise a false positive).
4. **Error kinds** are not compared.
5. **Dictionaries.** None is supplied, so FDICT streams are rejected by every side.
6. **miniz_oxide** ignores bytes after the stream, has no gzip support and is only run raw or zlib.
