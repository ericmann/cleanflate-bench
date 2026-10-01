# Fragments: cf vs zlib (test)

Verdicts live in `config/similarity_verdicts.toml` under `[cf_zlib]` keyed by fragment id; allowed values: `RFC-forced`, `idiomatic-inevitable`, `suspicious`.

## 1. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 22-33

```
    FLAGS,      /* i: waiting for method and flags (gzip) */
    TIME,       /* i: waiting for modification time (gzip) */
    OS,         /* i: waiting for extra flags and operating system (gzip) */
    EXLEN,      /* i: waiting for extra length (gzip) */
    EXTRA,      /* i: waiting for extra bytes (gzip) */
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
```

## 2. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 23-34

```
    TIME,       /* i: waiting for modification time (gzip) */
    OS,         /* i: waiting for extra flags and operating system (gzip) */
    EXLEN,      /* i: waiting for extra length (gzip) */
    EXTRA,      /* i: waiting for extra bytes (gzip) */
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
```

## 3. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 24-35

```
    OS,         /* i: waiting for extra flags and operating system (gzip) */
    EXLEN,      /* i: waiting for extra length (gzip) */
    EXTRA,      /* i: waiting for extra bytes (gzip) */
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
```

## 4. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 25-36

```
    EXLEN,      /* i: waiting for extra length (gzip) */
    EXTRA,      /* i: waiting for extra bytes (gzip) */
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
```

## 5. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 26-37

```
    EXTRA,      /* i: waiting for extra bytes (gzip) */
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
```

## 6. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 27-38

```
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
```

## 7. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 28-39

```
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
```

## 8. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 29-40

```
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
```

## 9. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 30-41

```
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
```

## 10. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 31-42

```
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
```

## 11. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 32-43

```
        TYPE,       /* i: waiting for type bits, including last-flag bit */
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
```

## 12. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 33-44

```
        TYPEDO,     /* i: same, but skip check to exit inflate on new block */
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
```

## 13. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 34-45

```
        STORED,     /* i: waiting for stored size (length and complement) */
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
```

## 14. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 35-46

```
        COPY_,      /* i/o: same as COPY below, but only first time in */
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
            LIT,        /* o: waiting for output space to write literal */
```

## 15. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 36-47

```
        COPY,       /* i/o: waiting for input or output to copy stored block */
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
            LIT,        /* o: waiting for output space to write literal */
    CHECK,      /* i: waiting for 32-bit check value */
```

## 16. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 37-48

```
        TABLE,      /* i: waiting for dynamic block table lengths */
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
            LIT,        /* o: waiting for output space to write literal */
    CHECK,      /* i: waiting for 32-bit check value */
    LENGTH,     /* i: waiting for 32-bit length (gzip) */
```

## 17. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 38-49

```
        LENLENS,    /* i: waiting for code length code lengths */
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
            LIT,        /* o: waiting for output space to write literal */
    CHECK,      /* i: waiting for 32-bit check value */
    LENGTH,     /* i: waiting for 32-bit length (gzip) */
    DONE,       /* finished check, done -- remain here until reset */
```

## 18. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 39-50

```
        CODELENS,   /* i: waiting for length/lit and distance code lengths */
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
            LIT,        /* o: waiting for output space to write literal */
    CHECK,      /* i: waiting for 32-bit check value */
    LENGTH,     /* i: waiting for 32-bit length (gzip) */
    DONE,       /* finished check, done -- remain here until reset */
    BAD,        /* got a data error -- remain here until reset */
```

## 19. `b8b547fc59e8` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 40-51

```
            LEN_,       /* i: same as LEN below, but only first time in */
            LEN,        /* i: waiting for length/lit/eob code */
            LENEXT,     /* i: waiting for length extra bits */
            DIST,       /* i: waiting for distance code */
            DISTEXT,    /* i: waiting for distance extra bits */
            MATCH,      /* o: waiting for output space to copy string */
            LIT,        /* o: waiting for output space to write literal */
    CHECK,      /* i: waiting for 32-bit check value */
    LENGTH,     /* i: waiting for 32-bit length (gzip) */
    DONE,       /* finished check, done -- remain here until reset */
    BAD,        /* got a data error -- remain here until reset */
    MEM,        /* got an inflate() memory error -- remain here until reset */
```

## 20. `99bd29cb1f3b` (23 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 144-166

```
    BadHeader,
    /// See [`Error::PresetDictionaryRequired`].
    PresetDictionaryRequired,
    /// See [`Error::DictionaryMismatch`].
    DictionaryMismatch,
    /// See [`Error::BadBlockType`].
    BadBlockType,
    /// See [`Error::InvalidStoredLength`].
    InvalidStoredLength,
    /// See [`Error::InvalidHuffmanTable`].
    InvalidHuffmanTable,
    /// See [`Error::InvalidSymbol`].
    InvalidSymbol,
    /// See [`Error::InvalidDistance`].
    InvalidDistance,
    /// See [`Error::ChecksumMismatch`].
    ChecksumMismatch,
    /// See [`Error::Truncated`].
    Truncated,
    /// See [`Error::TrailingData`].
    TrailingData,
    /// See [`Error::OutputLimitExceeded`].
    OutputLimitExceeded,
```

zlib: `inflate.h` lines 21-32

```
    HEAD = 16180,   /* i: waiting for magic header */
    FLAGS,      /* i: waiting for method and flags (gzip) */
    TIME,       /* i: waiting for modification time (gzip) */
    OS,         /* i: waiting for extra flags and operating system (gzip) */
    EXLEN,      /* i: waiting for extra length (gzip) */
    EXTRA,      /* i: waiting for extra bytes (gzip) */
    NAME,       /* i: waiting for end of file name (gzip) */
    COMMENT,    /* i: waiting for end of comment (gzip) */
    HCRC,       /* i: waiting for header crc (gzip) */
    DICTID,     /* i: waiting for dictionary check value */
    DICT,       /* waiting for inflateSetDictionary() call */
        TYPE,       /* i: waiting for type bits, including last-flag bit */
```
