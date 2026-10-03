# Findings

Bugs found in cleanflate are recorded here for the cleanflate repo. They are never patched in this repo (SPEC §6).

## Generated gzip fixtures are host-dependent (missed by the build's review stage)

- What: `testdata/MANIFEST.json` records the SHA-256 of every generated fixture. The oracle generates the 338 gzip-framed fixtures with the zlib bundled in libz-sys, which writes its compile-time `OS_CODE` into the gzip header OS byte. That is 3 on Linux and 19 under `__APPLE__`. On macOS, `oracle generate --tier full --locked` at v0.3.0-cleanroom (85f2100) reports a hash mismatch for every gzip fixture and refuses (338 problems), so the conformance corpus cannot be regenerated off Linux.
- Impact: the OS byte does not change the decompressed output, so only the recorded fixture hashes are host-dependent. It blocked `make conformance` on M-A until the Linux-generated files were copied from M-B (`config/session_notes.toml`, note `m-a-fixtures`).
- Why it was missed: the build, its CI and every Foundry review round ran on Linux. No round in `docs/REVIEW.md`, `docs/phase-1/REVIEW.md` or `docs/phase-2/REVIEW.md` mentions the OS byte or host dependence.
- Suggested fix (for the cleanflate repo; not patched here): set the gzip header explicitly, for example `deflateSetHeader` with `os = 255` as the hand-built malformed fixtures already do, or hash the fixture with byte 9 masked.
