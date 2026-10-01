# Structural comparison: cleanflate against zlib, zlib-ng, zlib-rs and miniz_oxide

Hand-written reading of the decompression paths (file set: `config/decomp_paths.toml`). The clean room
is lifted in this repo, so comparator source was read directly. Citations are
`<subject>:<path>:<line>` against the pinned versions below; paths are relative to each subject's source
root (zrs is the `zlib-rs` crate, which holds the inflate code).

Pinned versions (from `subjects.lock.json`):

| Subject | Version | Pin |
|---|---|---|
| cf | tag `v0.3.0-cleanroom` | git `85f210084a367dcc706c732f5776bf0563cdc0cd` |
| zlib | 1.3.2 | tarball sha256 `bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16` |
| zng | zlib-ng 2.3.3 | tarball sha256 `f9c65aa9c852eb8255b636fd9f07ce1c406f061ec19a2e7d508b318ca0c907d1` |
| zrs | zlib-rs 0.6.8 (via libz-rs-sys 0.6.8) | crate checksum `b268e58e7c69...` (core), see lock for the full value |
| mox | miniz_oxide 0.9.1 | crate checksum `b63fbc4a5086...` |

Feature-parity note: cf decompresses only, with no SIMD, no `unsafe` and no C ABI; comparators implement
compression and some have SIMD paths, hardware CRC and ABI compatibility. This write-up compares shapes,
not speed, and makes no claim about which design is better.

## 1. Bit reader

| Subject | Design | Where |
|---|---|---|
| cf | Separate resumable `BitReader`: `u64` buffer plus count. `fill` loads bytes until `need` bits are held; `refill_bulk` takes one little-endian 64-bit read when 8 bytes remain; `give_back` returns whole unread bytes to the input at exit. The exact-fill path holds at most 7 bits between steps. | cf:src/bitreader.rs:15, cf:src/bitreader.rs:51, cf:src/bitreader.rs:81, cf:src/bitreader.rs:129 |
| zlib | No reader type. `hold` and `bits` are locals manipulated by macros (`LOAD`, `RESTORE`, `INITBITS`, `PULLBYTE`, `NEEDBITS`, `BITS`, `DROPBITS`); the fast loop refills two bytes at a time when `bits < 15` and gives whole bytes back at exit. | zlib:inflate.c:328, zlib:inflate.c:368, zlib:inffast.c:100, zlib:inffast.c:290 |
| zng | Same macro structure with a 64-bit `hold` field; the fast loop template returns unused bytes the same way. | zng:inflate_p.h:106, zng:inflate.h:123, zng:inffast_tpl.h:300 |
| zrs | A `BitReader` struct over raw pointers with a `u64` `bit_buffer` and `bits_used`; `need_bits`, `bits`, `drop_bits`, and an `unsafe` word `refill` that requires 8 readable bytes. | zrs:src/inflate/bitreader.rs:6, zrs:src/inflate/bitreader.rs:86, zrs:src/inflate/bitreader.rs:123, zrs:src/inflate/bitreader.rs:137 |
| mox | No reader type: `bit_buf` and `num_bits` are fields of the local-variable struct threaded through the state functions, with `read_bits` and `pad_to_bytes` helpers. | mox:src/inflate/core.rs:1065, mox:src/inflate/core.rs:756, mox:src/inflate/core.rs:788 |

cf and zrs both isolate the reader in its own struct with a `u64` accumulator and bulk refill; zlib and
zng use macros over locals, and mox threads a local struct. cf's `give_back` (return whole buffered bytes
to the input at exit) is the same idea as the "return unused bytes" step at the end of zlib's and zng's
fast loops (zlib:inffast.c:290, zng:inffast_tpl.h:300). cf's design note for it is `D-27` in cleanflate's
`docs/DESIGN.md:721`. Differences: cf's reader is safe and bounds-checked per access; zrs's refill is
`unsafe` and pointer based.

## 2. Huffman table strategy

| Subject | Design | Where |
|---|---|---|
| cf | Canonical codes built into a lookup table whose entries are packed `u32` values (`Invalid`, `Symbol`, `Sub`); a first level of 2^10 entries for literal/length and 2^8 for distance, with second-level tables for longer codes. The code-length alphabet uses one 7-bit level. A bit-serial decoder exists as the reference path. | cf:src/huffman.rs:29, cf:src/huffman.rs:57, cf:src/huffman.rs:290, cf:src/config.rs:39, cf:src/config.rs:49 |
| zlib | `inflate_table` builds root plus sub-tables of 4-byte `code` records. Root bits are 7 for the code-length alphabet, 9 for literal/length and 6 for distance; table space is bounded by the `ENOUGH` constants (852 and 592). | zlib:inftrees.c:46, zlib:inftrees.h:49, zlib:inflate.c:812, zlib:inflate.c:890, zlib:inflate.c:899 |
| zng | `zng_inflate_table` (same algorithm), root bits 7, 10 for literal/length (distance 9 for the fixed table at 305-307) and larger `ENOUGH_LENS` (1332). | zng:inftrees.c:30, zng:inftrees.h:52, zng:inflate.c:831, zng:inflate.c:903, zng:inflate.c:305 |
| zrs | `inflate_table` ported with the same shape (`CodeType`, `used > ENOUGH` checks), root bits 7 for the code-length codes and the root returned by the builder for the others. | zrs:src/inflate/inftrees.rs:118, zrs:src/inflate/inftrees.rs:212, zrs:src/inflate.rs:1642, zrs:src/inflate.rs:1655 |
| mox | A different scheme: a 10-bit fast lookup (`look_up: [i16; 1024]`) for short codes plus a full binary tree walked bit by bit for longer ones. | mox:src/inflate/core.rs:47, mox:src/inflate/core.rs:74, mox:src/inflate/core.rs:80, mox:src/inflate/core.rs:134 |

The two-level root-plus-subtable layout is shared by cf, zlib, zng and zrs; mox is the odd one out with
a single fast table plus a tree. cf's packing (`Entry` kinds with a length and payload in one `u32`) and
its entry kinds are not zlib's `code` struct (`op`, `bits`, `val`). Table-size constants differ per
subject (cf 10 and 8, zlib 9 and 6, zng 10 and 9, mox 10 plus tree); cf documents its sizes as the
outcome of its own measured sweeps (`cf:src/config.rs:28-49`). cf has no `ENOUGH` constant: its builder
sizes tables from the lengths it is given.

## 3. Window management

| Subject | Design | Where |
|---|---|---|
| cf | A 32 KiB ring (`Window`) that only keeps what must survive across calls; within one call the output sink doubles as history, and the window is refreshed from output at every exit. Matches copy through slices (`Fast`) or byte by byte (`Reference`), with an overlapping-copy rule. | cf:src/window.rs:18, cf:src/window.rs:55, cf:src/window.rs:166, cf:src/window.rs:186 |
| zlib | Optional circular window allocated on first use (`updatewindow`), tracked by `wsize`, `whave`, `wnext`; copies the tail of the output into it at call exit. | zlib:inflate.c:252, zlib:inflate.h:97 |
| zng | The same `updatewindow` scheme, with a padded real buffer size (`wbufsize`) so chunked copies may overrun safely. | zng:inflate.c:324, zng:inflate.h:117 |
| zrs | `Window` over a weak slice with `have` and `next` fields, plus a `Writer` with `copy_match` and SIMD-dispatched `copy_match_help`. | zrs:src/inflate/window.rs:13, zrs:src/inflate/writer.rs:212, zrs:src/inflate/writer.rs:266 |
| mox | The 32 KiB dictionary lives in the output buffer itself (`TINFL_LZ_DICT_SIZE`), addressed with a size mask; `apply_match` and `transfer` copy within it. | mox:src/inflate/core.rs:42, mox:src/inflate/core.rs:1074, mox:src/inflate/core.rs:1154, mox:src/inflate/output_buffer.rs:6 |

cf's "sink is the history within a call, window refreshed at exit" resembles the zlib family's
"decode directly into the output buffer, copy the tail into the window at exit" in outcome, and zrs's
`have`/`next` field names mirror zlib's `whave`/`wnext`; cf's ring tracks a single running total and uses
absolute-index arithmetic (`cf:src/window.rs:19-24`) instead. cf has no padded buffer or SIMD chunk
copies.

## 4. Fast-loop design

| Subject | Design | Where |
|---|---|---|
| cf | One safe loop that runs only while input and output margins hold (16 input bytes, 258 output bytes), so no step inside an iteration can run short; an iteration is budgeted at 15+5+15+13 bits. It exits to the state machine at a margin, end of block, copy tail or error. | cf:src/fast_loop.rs:63, cf:src/fast_loop.rs:25, cf:src/config.rs:60, cf:src/config.rs:68 |
| zlib | `inflate_fast`: pointer-based loop with `lcode`/`dcode` masks, a two-byte refill when `bits < 15`, `goto dolen/dodist` for chained codes; entry assumptions documented at the top. | zlib:inffast.c:50, zlib:inffast.c:23, zlib:inffast.c:101, zlib:inffast.c:108 |
| zng | The same loop as a template (`INFLATE_FAST`) with `INFLATE_FAST_MIN_HAVE` and `INFLATE_FAST_MIN_LEFT` margins, `last`/`end` guard pointers and `CHUNKCOPY` variants. | zng:inffast_tpl.h:53, zng:inffast_tpl.h:25, zng:inffast_tpl.h:121, zng:inffast_tpl.h:238 |
| zrs | `inflate_fast_help` dispatching at run time to an AVX2 or a vanilla instantiation of one generic body. | zrs:src/inflate.rs:1880, zrs:src/inflate.rs:1899, zrs:src/inflate.rs:1908, zrs:src/inflate.rs:1918 |
| mox | `decompress_fast`, which copies the most-used variables into locals for register use and returns `(status, State)` so the slow path can resume. | mox:src/inflate/core.rs:1221 |

All five have a margin-guarded fast loop that hands control back to a general state machine near buffer
edges; that is the standard shape since zlib's `inflate_fast`. cf's loop is distinguished by being
margin-bounded with a fixed per-iteration bit budget instead of pointer sentinels, by indexing a
fixed-size first table level, and by being safe code; zng and zrs add vector copies that cf lacks.

## 5. State-machine shape

| Subject | Design | Where |
|---|---|---|
| cf | A Rust `enum State` for the DEFLATE body only (BlockHeader, StoredLen, StoredCopy, DynHeader, CodeLenLens, CodeLens, Repeat, LitLen, LenExtra, Dist, DistExtra, Copy, Done, Failed), some variants carrying data; dispatched by a `match` loop in `step_inner`. zlib and gzip wrappers are separate modules. Errors are sticky via `Failed`. | cf:src/inflate.rs:36, cf:src/inflate.rs:326, cf:src/inflate.rs:345 |
| zlib | An `inflate_mode` enum numbered from 16180 covering the wrapper and the body (HEAD ... TYPE, STORED, COPY, TABLE, LENLENS, CODELENS, LEN, LENEXT, DIST, DISTEXT, MATCH, CHECK, DONE) dispatched by one `switch` with fall-through. | zlib:inflate.h:20, zlib:inflate.c:505, zlib:inflate.c:747, zlib:inflate.c:914, zlib:inflate.c:1020 |
| zng | The same enum and `switch`. | zng:inflate.h:29, zng:inflate.c:507 |
| zrs | A `Mode` enum with zlib's names (Head, Flags, Time, Os, ExLen, Extra, Name, Comment, HCrc, ... Len_, Len, Lit, LenExt, Dist, DistExt, Match, Table ...), dispatched in a labelled loop. | zrs:src/inflate.rs:288, zrs:src/inflate.rs:896, zrs:src/inflate.rs:924 |
| mox | An `enum State` (Start, ReadZlibCmf, ReadZlibFlg, ReadBlockHeader, ...) driven by a `generate_state!` macro that turns `Action`s into jumps. | mox:src/inflate/core.rs:436, mox:src/inflate/core.rs:1049 |

cf's body states map closely onto zlib's: StoredLen/StoredCopy to STORED/COPY, CodeLenLens/CodeLens to
LENLENS/CODELENS, LitLen/LenExtra/Dist/DistExtra/Copy to LEN/LENEXT/DIST/DISTEXT/MATCH. That ordering
follows the sequence of RFC 1951 sections 3.2.3 to 3.2.7, so any correct incremental decoder has these
steps. What differs: cf has no HEAD..CHECK wrapper states in this enum, carries data in variants where
zlib keeps fields on a shared state struct, returns a sticky `Failed(Error)` where zlib sets `BAD`, and
uses no `switch` fall-through. zrs's enum reuses zlib's names almost one for one (consistent with
zlib-rs documenting that it is derived from zlib); mox's states and macro driver are unlike the others.

## 6. Observations relevant to the contamination question

Stated plainly, without speculation about how any implementation came to exist:

1. State decomposition and ordering in cf closely parallel zlib's (section 5). The correspondence is
   one-to-one for the DEFLATE body. It is also what the RFC's section order dictates, and mox, which
   also implements the RFC, uses a different decomposition and a different driver.
2. The two-level root-plus-subtable lookup is common to cf, zlib, zng and zrs (section 2). The entry
   encoding, table sizes and absence of `ENOUGH` constants differ in cf, and mox shows that the scheme
   is not forced.
3. cf's "give back whole unread bytes at exit" step has a direct counterpart in zlib and zng
   (sections 1 and 4). It is a standard consequence of a bulk refill with resumable streaming.
4. cf differs from the zlib family in: a separate safe `BitReader` type; payload-carrying state variants;
   wrapper handling outside the state machine; margin-based fast-loop entry with a fixed per-iteration bit
   budget; a sink-as-history window; and a dual `Fast`/`Reference` decode path. It differs from mox in
   nearly every structural choice listed above.
5. zrs mirrors zlib's naming and structure far more than cf does (Mode names, `have`/`next`, `inflate_table`
   port), which matches the documented derivation and is what the positive control is meant to show.
6. The token and identifier scores (`results/similarity_statement.md`) measure surface and token-level
   similarity, not these structural properties. In the generated statement, cf sits between the
   controls on two identifier metrics, so the structural resemblance noted in item 1 should be read
   together with that result and with the fragment review in `results/similarity_fragments/`, where
   verdicts are still pending a human.

Limits: the mapping of states to zlib modes is by reading, not by tooling; the line citations are a
snapshot of the pinned versions and are not machine-checked.
