# Fragments: cf vs mox (test)

Verdicts live in `config/similarity_verdicts.toml` under `[cf_mox]` keyed by fragment id; allowed values: `RFC-forced`, `idiomatic-inevitable`, `suspicious`.

## 1. `cb6eb451dab8` (43 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 172-179

```
        match self {
            ErrorKind::BadHeader => "BadHeader",
            ErrorKind::PresetDictionaryRequired => "PresetDictionaryRequired",
            ErrorKind::DictionaryMismatch => "DictionaryMismatch",
            ErrorKind::BadBlockType => "BadBlockType",
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
            ErrorKind::InvalidSymbol => "InvalidSymbol",
```

mox: `src/inflate/mod.rs` lines 114-121

```
        f.write_str(match self.status {
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 2. `61397453485a` (42 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 174-180

```
            ErrorKind::PresetDictionaryRequired => "PresetDictionaryRequired",
            ErrorKind::DictionaryMismatch => "DictionaryMismatch",
            ErrorKind::BadBlockType => "BadBlockType",
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
            ErrorKind::InvalidSymbol => "InvalidSymbol",
            ErrorKind::InvalidDistance => "InvalidDistance",
```

mox: `src/inflate/mod.rs` lines 115-121

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 3. `61397453485a` (42 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 175-181

```
            ErrorKind::DictionaryMismatch => "DictionaryMismatch",
            ErrorKind::BadBlockType => "BadBlockType",
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
            ErrorKind::InvalidSymbol => "InvalidSymbol",
            ErrorKind::InvalidDistance => "InvalidDistance",
            ErrorKind::ChecksumMismatch => "ChecksumMismatch",
```

mox: `src/inflate/mod.rs` lines 115-121

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 4. `61397453485a` (42 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 176-182

```
            ErrorKind::BadBlockType => "BadBlockType",
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
            ErrorKind::InvalidSymbol => "InvalidSymbol",
            ErrorKind::InvalidDistance => "InvalidDistance",
            ErrorKind::ChecksumMismatch => "ChecksumMismatch",
            ErrorKind::Truncated => "Truncated",
```

mox: `src/inflate/mod.rs` lines 115-121

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 5. `61397453485a` (42 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 177-183

```
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
            ErrorKind::InvalidSymbol => "InvalidSymbol",
            ErrorKind::InvalidDistance => "InvalidDistance",
            ErrorKind::ChecksumMismatch => "ChecksumMismatch",
            ErrorKind::Truncated => "Truncated",
            ErrorKind::TrailingData => "TrailingData",
```

mox: `src/inflate/mod.rs` lines 115-121

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 6. `61397453485a` (42 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 178-184

```
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
            ErrorKind::InvalidSymbol => "InvalidSymbol",
            ErrorKind::InvalidDistance => "InvalidDistance",
            ErrorKind::ChecksumMismatch => "ChecksumMismatch",
            ErrorKind::Truncated => "Truncated",
            ErrorKind::TrailingData => "TrailingData",
            ErrorKind::OutputLimitExceeded => "OutputLimitExceeded",
```

mox: `src/inflate/mod.rs` lines 115-121

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 7. `5d97bbe31505` (42 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 80-87

```
}

const FTEXT: u8 = 0x01;
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
const RESERVED: u8 = 0xE0;
```

mox: `src/inflate/core.rs` lines 123-136

```
}

/// The number of huffman tables used.
const MAX_HUFF_TABLES: usize = 3;
/// The length of the first (literal/length) huffman table.
const MAX_HUFF_SYMBOLS_0: usize = 288;
/// The length of the second (distance) huffman table.
const MAX_HUFF_SYMBOLS_1: usize = 32;
/// The length of the last (huffman code length) huffman table.
const MAX_HUFF_SYMBOLS_2: usize = 19;
/// The maximum length of a code that can be looked up in the fast lookup table.
const FAST_LOOKUP_BITS: u8 = 10;
/// The size of the fast lookup table.
const FAST_LOOKUP_SIZE: u16 = 1 << FAST_LOOKUP_BITS;
```

## 8. `981752dddb9c` (37 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 238-244

```
        let msg = match self {
            HuffmanError::OverSubscribed => "Huffman code table is over-subscribed",
            HuffmanError::Incomplete => "Huffman code table is incomplete",
            HuffmanError::TooManyLengthCodes => "too many code-length symbols transmitted",
            HuffmanError::RepeatWithoutPrevious => "repeat code with no previous code length",
            HuffmanError::RepeatOverflow => "repeat code overruns the code-length sequence",
            HuffmanError::MissingEndOfBlock => "literal/length table has no end-of-block code",
```

mox: `src/inflate/mod.rs` lines 114-120

```
        f.write_str(match self.status {
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
```

## 9. `b4e8e5cafb27` (37 tokens)

Verdict: (none yet)

cf: `src/stats.rs` lines 80-92

```
    pub window_bytes_written: u64,
    /// Entries into a specialised fast decode loop.
    pub fast_loop_entries: u64,
    /// Symbols decoded inside that loop.
    pub fast_loop_symbols: u64,
    /// Output-buffer growths made by `decompress_with_stats`.
    pub oneshot_resizes: u64,
    /// Bytes added by those growths.
    pub oneshot_bytes_allocated: u64,
}

#[cfg(feature = "stats")]
impl Stats {
```

mox: `src/inflate/core.rs` lines 229-245

```
    pub num_bits: u8,

    /// The `num_bits` MSBs from the last byte of input consumed,
    /// that are needed for decoding the next deflate block.
    /// Stored in the LSBs of this field.
    pub bit_buf: u8,

    /// Zlib CMF
    pub z_header0: u32,
    /// Zlib FLG
    pub z_header1: u32,
    /// Adler32 checksum of the data decompressed so far
    pub check_adler32: u32,
}

#[cfg(feature = "block-boundary")]
impl Default for BlockBoundaryState {
```

## 10. `9c1006dc7742` (36 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 173-178

```
            ErrorKind::BadHeader => "BadHeader",
            ErrorKind::PresetDictionaryRequired => "PresetDictionaryRequired",
            ErrorKind::DictionaryMismatch => "DictionaryMismatch",
            ErrorKind::BadBlockType => "BadBlockType",
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
            ErrorKind::InvalidHuffmanTable => "InvalidHuffmanTable",
```

mox: `src/inflate/mod.rs` lines 116-121

```
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 11. `9c1006dc7742` (36 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 179-184

```
            ErrorKind::InvalidSymbol => "InvalidSymbol",
            ErrorKind::InvalidDistance => "InvalidDistance",
            ErrorKind::ChecksumMismatch => "ChecksumMismatch",
            ErrorKind::Truncated => "Truncated",
            ErrorKind::TrailingData => "TrailingData",
            ErrorKind::OutputLimitExceeded => "OutputLimitExceeded",
```

mox: `src/inflate/mod.rs` lines 115-120

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
```

## 12. `9c1006dc7742` (36 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 239-244

```
            HuffmanError::OverSubscribed => "Huffman code table is over-subscribed",
            HuffmanError::Incomplete => "Huffman code table is incomplete",
            HuffmanError::TooManyLengthCodes => "too many code-length symbols transmitted",
            HuffmanError::RepeatWithoutPrevious => "repeat code with no previous code length",
            HuffmanError::RepeatOverflow => "repeat code overruns the code-length sequence",
            HuffmanError::MissingEndOfBlock => "literal/length table has no end-of-block code",
```

mox: `src/inflate/mod.rs` lines 116-121

```
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 13. `011e45a65406` (35 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 82-87

```
const FTEXT: u8 = 0x01;
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
const RESERVED: u8 = 0xE0;
```

mox: `src/inflate/core.rs` lines 137-142

```
const MAX_HUFF_TREE_SIZE: usize = MAX_HUFF_SYMBOLS_0 * 2;
const LITLEN_TABLE: usize = 0;
const DIST_TABLE: usize = 1;
const HUFFLEN_TABLE: usize = 2;
const LEN_CODES_SIZE: usize = 512;
const LEN_CODES_MASK: usize = LEN_CODES_SIZE - 1;
```

## 14. `07d1df933328` (35 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 83-87

```
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
const RESERVED: u8 = 0xE0;
```

mox: `src/inflate/core.rs` lines 126-134

```
const MAX_HUFF_TABLES: usize = 3;
/// The length of the first (literal/length) huffman table.
const MAX_HUFF_SYMBOLS_0: usize = 288;
/// The length of the second (distance) huffman table.
const MAX_HUFF_SYMBOLS_1: usize = 32;
/// The length of the last (huffman code length) huffman table.
const MAX_HUFF_SYMBOLS_2: usize = 19;
/// The maximum length of a code that can be looked up in the fast lookup table.
const FAST_LOOKUP_BITS: u8 = 10;
```

## 15. `0b2f1742b13d` (34 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 82-86

```
const FTEXT: u8 = 0x01;
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
```

mox: `src/inflate/core.rs` lines 128-136

```
const MAX_HUFF_SYMBOLS_0: usize = 288;
/// The length of the second (distance) huffman table.
const MAX_HUFF_SYMBOLS_1: usize = 32;
/// The length of the last (huffman code length) huffman table.
const MAX_HUFF_SYMBOLS_2: usize = 19;
/// The maximum length of a code that can be looked up in the fast lookup table.
const FAST_LOOKUP_BITS: u8 = 10;
/// The size of the fast lookup table.
const FAST_LOOKUP_SIZE: u16 = 1 << FAST_LOOKUP_BITS;
```

## 16. `c7952f0714fb` (33 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 82-86

```
const FTEXT: u8 = 0x01;
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
```

mox: `src/inflate/core.rs` lines 138-142

```
const LITLEN_TABLE: usize = 0;
const DIST_TABLE: usize = 1;
const HUFFLEN_TABLE: usize = 2;
const LEN_CODES_SIZE: usize = 512;
const LEN_CODES_MASK: usize = LEN_CODES_SIZE - 1;
```

## 17. `a3c4482ddc15` (31 tokens)

Verdict: (none yet)

cf: `src/stats.rs` lines 24-35

```
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Stats {
    /// Calls to the inflater's `step`.
    pub step_calls: u64,
    /// Iterations of `step`'s state loop.
    pub state_dispatches: u64,
    /// Bytes written to the caller's output.
    pub output_bytes: u64,
    /// Stored blocks started.
    pub blocks_stored: u64,
    /// Fixed-Huffman blocks started.
    pub blocks_fixed: u64,
```

mox: `src/inflate/core.rs` lines 224-241

```
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct BlockBoundaryState {
    /// The number of bits from the last byte of input consumed,
    /// that are needed for decoding the next deflate block.
    /// Value is in range `0..=7`
    pub num_bits: u8,

    /// The `num_bits` MSBs from the last byte of input consumed,
    /// that are needed for decoding the next deflate block.
    /// Stored in the LSBs of this field.
    pub bit_buf: u8,

    /// Zlib CMF
    pub z_header0: u32,
    /// Zlib FLG
    pub z_header1: u32,
    /// Adler32 checksum of the data decompressed so far
    pub check_adler32: u32,
```

## 18. `e5c46942e853` (30 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 173-177

```
            ErrorKind::BadHeader => "BadHeader",
            ErrorKind::PresetDictionaryRequired => "PresetDictionaryRequired",
            ErrorKind::DictionaryMismatch => "DictionaryMismatch",
            ErrorKind::BadBlockType => "BadBlockType",
            ErrorKind::InvalidStoredLength => "InvalidStoredLength",
```

mox: `src/inflate/mod.rs` lines 117-121

```
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```

## 19. `e5c46942e853` (30 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 180-184

```
            ErrorKind::InvalidDistance => "InvalidDistance",
            ErrorKind::ChecksumMismatch => "ChecksumMismatch",
            ErrorKind::Truncated => "Truncated",
            ErrorKind::TrailingData => "TrailingData",
            ErrorKind::OutputLimitExceeded => "OutputLimitExceeded",
```

mox: `src/inflate/mod.rs` lines 115-119

```
            TINFLStatus::FailedCannotMakeProgress => "Truncated input stream",
            TINFLStatus::BadParam => "Invalid output buffer size",
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
```

## 20. `e5c46942e853` (30 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 239-243

```
            HuffmanError::OverSubscribed => "Huffman code table is over-subscribed",
            HuffmanError::Incomplete => "Huffman code table is incomplete",
            HuffmanError::TooManyLengthCodes => "too many code-length symbols transmitted",
            HuffmanError::RepeatWithoutPrevious => "repeat code with no previous code length",
            HuffmanError::RepeatOverflow => "repeat code overruns the code-length sequence",
```

mox: `src/inflate/mod.rs` lines 117-121

```
            TINFLStatus::Adler32Mismatch => "Adler32 checksum mismatch",
            TINFLStatus::Failed => "Invalid input data",
            TINFLStatus::Done => "", // Unreachable
            TINFLStatus::NeedsMoreInput => "Truncated input stream",
            TINFLStatus::HasMoreOutput => "Output size exceeded the specified limit",
```
