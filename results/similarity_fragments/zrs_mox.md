# Fragments: zrs vs mox (negative)

Verdicts live in `config/similarity_verdicts.toml` under `[zrs_mox]` keyed by fragment id; allowed values: `RFC-forced`, `idiomatic-inevitable`, `suspicious`.

## 1. `fca472f60987` (43 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 410-435

```
    writer: Writer<'a>,
    total: usize,

    /// length of a block to copy
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,

    gzip_flags: i32,

    checksum: u32,
```

mox: `src/inflate/core.rs` lines 263-287

```
    state: core::State,
    /// Number of bits in the bit buffer.
    num_bits: u32,
    /// Zlib CMF
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
    /// Number of entries in each huffman table.
    table_sizes: [u16; MAX_HUFF_TABLES],
```

## 2. `fca472f60987` (43 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 411-436

```
    total: usize,

    /// length of a block to copy
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,

    gzip_flags: i32,

    checksum: u32,
    crc_fold: Crc32Fold,
```

mox: `src/inflate/core.rs` lines 263-287

```
    state: core::State,
    /// Number of bits in the bit buffer.
    num_bits: u32,
    /// Zlib CMF
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
    /// Number of entries in each huffman table.
    table_sizes: [u16; MAX_HUFF_TABLES],
```

## 3. `501f9ae5781f` (39 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 410-433

```
    writer: Writer<'a>,
    total: usize,

    /// length of a block to copy
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,

    gzip_flags: i32,
```

mox: `src/inflate/core.rs` lines 265-287

```
    num_bits: u32,
    /// Zlib CMF
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
    /// Number of entries in each huffman table.
    table_sizes: [u16; MAX_HUFF_TABLES],
```

## 4. `501f9ae5781f` (39 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 414-436

```
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,

    gzip_flags: i32,

    checksum: u32,
    crc_fold: Crc32Fold,
```

mox: `src/inflate/core.rs` lines 263-285

```
    state: core::State,
    /// Number of bits in the bit buffer.
    num_bits: u32,
    /// Zlib CMF
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
```

## 5. `e70949e75d45` (35 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 410-431

```
    writer: Writer<'a>,
    total: usize,

    /// length of a block to copy
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,
```

mox: `src/inflate/core.rs` lines 267-287

```
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
    /// Number of entries in each huffman table.
    table_sizes: [u16; MAX_HUFF_TABLES],
```

## 6. `e70949e75d45` (35 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 416-436

```
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,

    gzip_flags: i32,

    checksum: u32,
    crc_fold: Crc32Fold,
```

mox: `src/inflate/core.rs` lines 263-283

```
    state: core::State,
    /// Number of bits in the bit buffer.
    num_bits: u32,
    /// Zlib CMF
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
```

## 7. `116544abf627` (34 tokens)

Verdict: (none yet)

zrs: `src/inflate/writer.rs` lines 9-16

```
    buf: WeakSliceMut<'a, MaybeUninit<u8>>,
    filled: usize,
}

impl<'a> Writer<'a> {
    /// Creates a new `Writer` from a fully initialized buffer.
    #[inline]
    pub fn new(buf: &'a mut [u8]) -> Writer<'a> {
```

mox: `src/inflate/output_buffer.rs` lines 8-15

```
    position: usize,
    max: usize,
}

impl<'a> OutputBuffer<'a> {
    #[inline]
    pub fn from_slice_pos_and_max(
        slice: &'a mut [u8],
```

## 8. `393ce865bf93` (32 tokens)

Verdict: (none yet)

zrs: `src/c_api.rs` lines 203-210

```
impl Default for gz_header {
    fn default() -> Self {
        Self {
            text: 0,
            time: 0,
            xflags: 0,
            os: 0,
            extra: core::ptr::null_mut(),
```

mox: `src/inflate/core.rs` lines 245-252

```
impl Default for BlockBoundaryState {
    fn default() -> Self {
        BlockBoundaryState {
            num_bits: 0,
            bit_buf: 0,
            z_header0: 0,
            z_header1: 0,
            check_adler32: 1,
```

## 9. `601e3923ddf5` (31 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 410-430

```
    writer: Writer<'a>,
    total: usize,

    /// length of a block to copy
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
```

mox: `src/inflate/core.rs` lines 269-287

```
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
    /// Number of entries in each huffman table.
    table_sizes: [u16; MAX_HUFF_TABLES],
```

## 10. `601e3923ddf5` (31 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 419-436

```
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,

    in_available: usize,
    out_available: usize,

    gzip_flags: i32,

    checksum: u32,
    crc_fold: Crc32Fold,
```

mox: `src/inflate/core.rs` lines 263-281

```
    state: core::State,
    /// Number of bits in the bit buffer.
    num_bits: u32,
    /// Zlib CMF
    z_header0: u32,
    /// Zlib FLG
    z_header1: u32,
    /// Adler32 checksum from the zlib header.
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
```

## 11. `aa46dcb847de` (28 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx2.rs` lines 169-172

```
    const INPUT: [u8; 1024] = {
        let mut array = [0; 1024];
        let mut i = 0;
        while i < array.len() {
```

mox: `src/inflate/core.rs` lines 855-859

```
    static REVERSED_BITS_LOOKUP: [u16; 512] = {
        let mut table = [0; 512];

        let mut i = 0;
        while i < 512 {
```

## 12. `6eb4567da9ab` (28 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512.rs` lines 240-243

```
    const INPUT: [u8; 128] = {
        let mut array = [0; 128];
        let mut i = 0;
        while i < array.len() {
```

mox: `src/inflate/core.rs` lines 855-859

```
    static REVERSED_BITS_LOOKUP: [u16; 512] = {
        let mut table = [0; 512];

        let mut i = 0;
        while i < 512 {
```

## 13. `e7933e55a66a` (28 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512_vnni.rs` lines 191-194

```
    const INPUT: [u8; 128] = {
        let mut array = [0; 128];
        let mut i = 0;
        while i < array.len() {
```

mox: `src/inflate/core.rs` lines 855-859

```
    static REVERSED_BITS_LOOKUP: [u16; 512] = {
        let mut table = [0; 512];

        let mut i = 0;
        while i < 512 {
```

## 14. `e1357e286eea` (28 tokens)

Verdict: (none yet)

zrs: `src/adler32/lsx.rs` lines 234-237

```
    const INPUT: [u8; 1024] = {
        let mut array = [0; 1024];
        let mut i = 0;
        while i < array.len() {
```

mox: `src/inflate/core.rs` lines 855-859

```
    static REVERSED_BITS_LOOKUP: [u16; 512] = {
        let mut table = [0; 512];

        let mut i = 0;
        while i < 512 {
```

## 15. `714616ba9a30` (28 tokens)

Verdict: (none yet)

zrs: `src/adler32/neon.rs` lines 245-248

```
    const INPUT: [u8; 1024] = {
        let mut array = [0; 1024];
        let mut i = 0;
        while i < array.len() {
```

mox: `src/inflate/core.rs` lines 855-859

```
    static REVERSED_BITS_LOOKUP: [u16; 512] = {
        let mut table = [0; 512];

        let mut i = 0;
        while i < 512 {
```

## 16. `a6a383abec64` (28 tokens)

Verdict: (none yet)

zrs: `src/crc32.rs` lines 128-131

```
    const INPUT: [u8; 1024] = {
        let mut array = [0; 1024];
        let mut i = 0;
        while i < array.len() {
```

mox: `src/inflate/core.rs` lines 855-859

```
    static REVERSED_BITS_LOOKUP: [u16; 512] = {
        let mut table = [0; 512];

        let mut i = 0;
        while i < 512 {
```

## 17. `baa5cc2a34b3` (28 tokens)

Verdict: (none yet)

zrs: `src/inflate/inftrees.rs` lines 306-311

```
    }

    #[test]
    fn generate_fixed_length_table() {
        let mut work = [0; 512];
        let generated = build_fixed_length_table(&mut work);
```

mox: `src/inflate/mod.rs` lines 363-370

```
    }

    #[test]
    fn test_decompress_slice_iter_to_slice() {
        // one slice
        let mut out = [0_u8; 12_usize];
        let r =
            decompress_slice_iter_to_slice(&mut out, Some(&ENCODED[..]).into_iter(), true, false);
```

## 18. `baa5cc2a34b3` (28 tokens)

Verdict: (none yet)

zrs: `src/inflate/inftrees.rs` lines 330-335

```
    }

    #[test]
    fn generate_fixed_distance_table() {
        let mut work = [0; 512];
        let generated = build_fixed_distance_table(&mut work);
```

mox: `src/inflate/mod.rs` lines 363-370

```
    }

    #[test]
    fn test_decompress_slice_iter_to_slice() {
        // one slice
        let mut out = [0_u8; 12_usize];
        let r =
            decompress_slice_iter_to_slice(&mut out, Some(&ENCODED[..]).into_iter(), true, false);
```

## 19. `3508e4c665f3` (27 tokens)

Verdict: (none yet)

zrs: `src/adler32/wasm.rs` lines 3-6

```
const MOD: u32 = 65521;
const NMAX: usize = 5552;
const BLOCK_SIZE: usize = 32;
const CHUNK_SIZE: usize = NMAX / BLOCK_SIZE * BLOCK_SIZE;
```

mox: `src/inflate/core.rs` lines 139-142

```
const DIST_TABLE: usize = 1;
const HUFFLEN_TABLE: usize = 2;
const LEN_CODES_SIZE: usize = 512;
const LEN_CODES_MASK: usize = LEN_CODES_SIZE - 1;
```

## 20. `4365a0c547a0` (27 tokens)

Verdict: (none yet)

zrs: `src/inflate.rs` lines 410-428

```
    writer: Writer<'a>,
    total: usize,

    /// length of a block to copy
    length: usize,
    /// distance back to copy the string from
    offset: usize,

    /// extra bits needed
    extra: usize,

    /// bits back of last unprocessed length/lit
    back: usize,

    /// initial length of match
    was: usize,

    /// size of memory copying chunk
    chunksize: usize,
```

mox: `src/inflate/core.rs` lines 271-287

```
    z_adler32: u32,
    /// 1 if the current block is the last block, 0 otherwise.
    finish: u8,
    /// The type of the current block.
    /// or if in a dynamic block, which huffman table we are currently
    // initializing.
    block_type: u8,
    /// 1 if the adler32 value should be checked.
    check_adler32: u32,
    /// Last match distance.
    dist: u32,
    /// Variable used for match length, symbols, and a number of other things.
    counter: u32,
    /// Number of extra bits for the last length or distance code.
    num_extra: u8,
    /// Number of entries in each huffman table.
    table_sizes: [u16; MAX_HUFF_TABLES],
```
