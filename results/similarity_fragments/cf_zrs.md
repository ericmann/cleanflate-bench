# Fragments: cf vs zrs (test)

Verdicts live in `config/similarity_verdicts.toml` under `[cf_zrs]` keyed by fragment id; allowed values: `RFC-forced`, `idiomatic-inevitable`, `suspicious`.

## 1. `66f174b99c8d` (38 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 104-110

```
    let (mut s1, mut s2) = adler_split(adler);
    for &byte in data {
        s1 = (s1 + byte as u32) % ADLER_MOD;
        s2 = (s2 + s1) % ADLER_MOD;
    }
    (s2 << 16) | s1
}
```

zrs: `src/adler32.rs` lines 95-103

```
    let mut b = (start_checksum >> 16) & 0xFFFF;

    for &byte in data {
        a = (a + byte as u32) % MOD_ADLER;
        b = (b + a) % MOD_ADLER;
    }

    (b << 16) | a
}
```

## 2. `b90e9057cb7f` (35 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 497-506

```
    pub(crate) fn total_out(&self) -> u64 {
        self.total_out
    }

    /// Every member started so far, retained or not.
    pub(crate) fn member_count(&self) -> u64 {
        self.member_count
    }

    pub(crate) fn is_done(&self) -> bool {
```

zrs: `src/weak_slice.rs` lines 45-53

```
    pub(crate) fn as_mut_ptr(&mut self) -> *mut T {
        self.ptr
    }

    pub(crate) fn len(&self) -> usize {
        self.len
    }

    pub(crate) fn is_empty(&self) -> bool {
```

## 3. `1e74d1b05b19` (34 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 495-503

```
    }

    pub(crate) fn total_out(&self) -> u64 {
        self.total_out
    }

    /// Every member started so far, retained or not.
    pub(crate) fn member_count(&self) -> u64 {
        self.member_count
```

zrs: `src/weak_slice.rs` lines 47-54

```
    }

    pub(crate) fn len(&self) -> usize {
        self.len
    }

    pub(crate) fn is_empty(&self) -> bool {
        self.len() == 0
```

## 4. `8775e1956207` (32 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 141-149

```
    while k < 8 {
        if c & 1 != 0 {
            c = CRC32_POLY ^ (c >> 1);
        } else {
            c >>= 1;
        }
        k += 1;
    }
    c
```

zrs: `src/crc32/braid.rs` lines 52-60

```
            while k < 8 * (W * N - i) {
                if c & 1 != 0 {
                    c = CRC32_LSB_POLY ^ (c >> 1);
                } else {
                    c >>= 1;
                }
                k += 1;
            }
            arr[i][j] = c as u32;
```

## 5. `8775e1956207` (32 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 156-164

```
    while k < 8 {
        if c & 1 != 0 {
            c = CRC32_POLY ^ (c >> 1);
        } else {
            c >>= 1;
        }
        k += 1;
    }
    c
```

zrs: `src/crc32/braid.rs` lines 52-60

```
            while k < 8 * (W * N - i) {
                if c & 1 != 0 {
                    c = CRC32_LSB_POLY ^ (c >> 1);
                } else {
                    c >>= 1;
                }
                k += 1;
            }
            arr[i][j] = c as u32;
```

## 6. `eef256911a77` (31 tokens)

Verdict: (none yet)

cf: `src/inflate.rs` lines 228-236

```
    }

    /// Total bytes produced so far across all calls to `step`.
    pub(crate) fn total_out(&self) -> u64 {
        self.total_out
    }

    /// Whether the final block has been fully decoded.
    pub(crate) fn is_done(&self) -> bool {
```

zrs: `src/weak_slice.rs` lines 47-53

```
    }

    pub(crate) fn len(&self) -> usize {
        self.len
    }

    pub(crate) fn is_empty(&self) -> bool {
```

## 7. `e5d9abe62a70` (30 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 7-10

```
use crate::checksum::Crc32;
use crate::decode_path::DecodePath;
use crate::error::{ChecksumKind, Error, HeaderError};
use crate::inflate::{InflateStatus, Inflater};
```

zrs: `src/inflate/infback.rs` lines 2-6

```
use core::marker::PhantomData;

use crate::allocate::Allocator;
use crate::c_api::{in_func, internal_state, out_func};
use crate::inflate::bitreader::BitReader;
```

## 8. `9f9def959111` (30 tokens)

Verdict: (none yet)

cf: `src/zlib.rs` lines 4-7

```
use crate::checksum::Adler32;
use crate::decode_path::DecodePath;
use crate::error::{ChecksumKind, Error, HeaderError};
use crate::inflate::{InflateStatus, Inflater};
```

zrs: `src/inflate/infback.rs` lines 2-6

```
use core::marker::PhantomData;

use crate::allocate::Allocator;
use crate::c_api::{in_func, internal_state, out_func};
use crate::inflate::bitreader::BitReader;
```

## 9. `4d5097066124` (28 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 189-191

```
impl fmt::Display for ErrorKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
```

zrs: `src/inflate/writer.rs` lines 415-417

```
impl fmt::Debug for Writer<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Writer")
```

## 10. `621058d329d6` (28 tokens)

Verdict: (none yet)

cf: `src/options.rs` lines 39-52

```
    pub dictionary: Option<Vec<u8>>,
    /// Maximum bytes retained per gzip FNAME/FCOMMENT/FEXTRA field.
    pub max_gzip_field: usize,
    /// Maximum number of parsed gzip member headers retained by a
    /// streaming decode (every member past this cap is still decoded and
    /// counted, just not kept in [`crate::Decoded::gzip_members`] /
    /// [`crate::Decompressor::gzip_headers`]).
    pub max_gzip_headers: usize,
}

impl Default for Options {
    fn default() -> Self {
        Options {
            max_output: DEFAULT_MAX_OUTPUT,
```

zrs: `src/c_api.rs` lines 196-206

```
    pub comm_max: u32,
    /// true if there was or will be a header crc
    pub hcrc: i32,
    /// true when done reading gzip header (not used when writing a gzip file)
    pub done: i32,
}

impl Default for gz_header {
    fn default() -> Self {
        Self {
            text: 0,
```

## 11. `78d3cb699be1` (26 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 82-85

```
const FTEXT: u8 = 0x01;
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
```

zrs: `src/adler32/wasm.rs` lines 3-6

```
const MOD: u32 = 65521;
const NMAX: usize = 5552;
const BLOCK_SIZE: usize = 32;
const CHUNK_SIZE: usize = NMAX / BLOCK_SIZE * BLOCK_SIZE;
```

## 12. `78d3cb699be1` (26 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 83-86

```
const FHCRC: u8 = 0x02;
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
```

zrs: `src/adler32/wasm.rs` lines 3-6

```
const MOD: u32 = 65521;
const NMAX: usize = 5552;
const BLOCK_SIZE: usize = 32;
const CHUNK_SIZE: usize = NMAX / BLOCK_SIZE * BLOCK_SIZE;
```

## 13. `78d3cb699be1` (26 tokens)

Verdict: (none yet)

cf: `src/gzip.rs` lines 84-87

```
const FEXTRA: u8 = 0x04;
const FNAME: u8 = 0x08;
const FCOMMENT: u8 = 0x10;
const RESERVED: u8 = 0xE0;
```

zrs: `src/adler32/wasm.rs` lines 3-6

```
const MOD: u32 = 65521;
const NMAX: usize = 5552;
const BLOCK_SIZE: usize = 32;
const CHUNK_SIZE: usize = NMAX / BLOCK_SIZE * BLOCK_SIZE;
```

## 14. `31f9a0967a9e` (26 tokens)

Verdict: (none yet)

cf: `src/huffman.rs` lines 12-16

```
const CODE_LENGTH_TABLE_BITS: u32 = 7;

const KIND_INVALID: u32 = 0;
const KIND_SYMBOL: u32 = 1;
const KIND_SUB: u32 = 2;
```

zrs: `src/adler32/wasm.rs` lines 3-6

```
const MOD: u32 = 65521;
const NMAX: usize = 5552;
const BLOCK_SIZE: usize = 32;
const CHUNK_SIZE: usize = NMAX / BLOCK_SIZE * BLOCK_SIZE;
```

## 15. `e95373360df6` (25 tokens)

Verdict: (none yet)

cf: `src/bitreader.rs` lines 43-51

```
    pub(crate) fn available(&self) -> u32 {
        self.count
    }

    /// Load whole bytes from `input[*pos..]` into the buffer, advancing
    /// `*pos`, until at least `need` bits are buffered or `input` is
    /// exhausted. Never loads a byte once `need` is already satisfied.
    /// Returns whether `need` bits are now available.
    pub(crate) fn fill(&mut self, input: &[u8], pos: &mut usize, need: u32) -> bool {
```

zrs: `src/weak_slice.rs` lines 49-53

```
    pub(crate) fn len(&self) -> usize {
        self.len
    }

    pub(crate) fn is_empty(&self) -> bool {
```

## 16. `8471682e59ec` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 215-216

```
impl fmt::Display for HeaderError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

zrs: `src/inflate/writer.rs` lines 415-416

```
impl fmt::Debug for Writer<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

## 17. `8471682e59ec` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 236-237

```
impl fmt::Display for HuffmanError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

zrs: `src/inflate/writer.rs` lines 415-416

```
impl fmt::Debug for Writer<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

## 18. `8471682e59ec` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 250-251

```
impl fmt::Display for ChecksumKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

zrs: `src/inflate/writer.rs` lines 415-416

```
impl fmt::Debug for Writer<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

## 19. `8471682e59ec` (24 tokens)

Verdict: (none yet)

cf: `src/error.rs` lines 262-263

```
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

zrs: `src/inflate/writer.rs` lines 415-416

```
impl fmt::Debug for Writer<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
```

## 20. `ca010a000189` (24 tokens)

Verdict: (none yet)

cf: `src/options.rs` lines 46-52

```
    pub max_gzip_headers: usize,
}

impl Default for Options {
    fn default() -> Self {
        Options {
            max_output: DEFAULT_MAX_OUTPUT,
```

zrs: `src/inflate.rs` lines 2221-2227

```
    pub window_bits: i32,
}

impl Default for InflateConfig {
    fn default() -> Self {
        Self {
            window_bits: DEF_WBITS,
```
