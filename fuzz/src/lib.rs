//! Differential fuzzing of cleanflate against zlib, libz-rs-sys and miniz_oxide (SPEC 3.6).
//!
//! The first input byte selects the framing and the rest is the compressed stream. Each side
//! decodes with a 64 MiB output cap. Normalizations (also listed in `fuzz/README.md`):
//!
//! 1. cf runs with `TrailingData::Allow`; the references stop at the end of the first stream, so
//!    trailing bytes never count as a difference.
//! 2. gzip: cf decodes every concatenated member, so the zlib-family references loop over members
//!    (reset and continue while the remaining input starts with the gzip magic `1f 8b`). This keeps
//!    "second member is bad" a real divergence instead of an API difference.
//! 3. Both sides exceeding the output cap counts as agreement.
//! 4. Only accept versus reject and the output bytes are compared; error kinds are not.
//! 5. No preset dictionary is supplied to anyone, so FDICT streams are rejected by all sides.

use std::ffi::{c_char, c_int, c_uint, c_ulong, c_void};

/// Output cap, in bytes, applied to every side.
pub const CAP: usize = 64 << 20;

/// Which framing the first input byte selected.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Framing {
    Raw,
    Zlib,
    Gzip,
}

/// What one decoder did with an input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Outcome {
    /// Accepted; the decoded bytes of the first stream (all members for gzip).
    Ok(Vec<u8>),
    /// Rejected (any error kind).
    Rejected,
    /// Would produce more than `CAP` bytes.
    Capped,
}

impl Outcome {
    /// Short description naming the outcome, used in divergence messages.
    pub fn describe(&self) -> String {
        match self {
            Outcome::Ok(v) => format!("accepted {} bytes (fnv {:016x})", v.len(), fnv(v)),
            Outcome::Rejected => "rejected".to_string(),
            Outcome::Capped => "hit the output cap".to_string(),
        }
    }
}

fn fnv(data: &[u8]) -> u64 {
    data.iter().fold(0xcbf2_9ce4_8422_2325, |h, b| {
        (h ^ u64::from(*b)).wrapping_mul(0x100_0000_01b3)
    })
}

/// Agreement rule: both capped, both rejected, or both accepted with identical bytes.
pub fn compare(left: &Outcome, right: &Outcome) -> Result<(), String> {
    match (left, right) {
        (Outcome::Capped, Outcome::Capped) | (Outcome::Rejected, Outcome::Rejected) => Ok(()),
        (Outcome::Ok(a), Outcome::Ok(b)) if a == b => Ok(()),
        _ => Err(format!(
            "divergence: {} vs {}",
            left.describe(),
            right.describe()
        )),
    }
}

/// cleanflate with trailing data allowed.
pub fn decode_cf(framing: Framing, input: &[u8]) -> Outcome {
    let format = match framing {
        Framing::Raw => cleanflate::Format::Raw,
        Framing::Zlib => cleanflate::Format::Zlib,
        Framing::Gzip => cleanflate::Format::Gzip,
    };
    let options = cleanflate::Options {
        max_output: CAP as u64,
        trailing: cleanflate::TrailingData::Allow,
        ..cleanflate::Options::default()
    };
    match cleanflate::decompress_with(format, input, &options) {
        Ok(d) => Outcome::Ok(d.data),
        Err(cleanflate::Error::OutputLimitExceeded { .. }) => Outcome::Capped,
        Err(_) => Outcome::Rejected,
    }
}

/// miniz_oxide (raw or zlib only; trailing bytes are ignored by the library). The low-level
/// decompressor is used so the zlib Adler-32 trailer can be verified explicitly.
pub fn decode_mox(framing: Framing, input: &[u8]) -> Outcome {
    use miniz_oxide::inflate::core::inflate_flags::{
        TINFL_FLAG_COMPUTE_ADLER32, TINFL_FLAG_PARSE_ZLIB_HEADER,
        TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF,
    };
    use miniz_oxide::inflate::core::{decompress, DecompressorOxide};
    use miniz_oxide::inflate::TINFLStatus;

    let mut flags = TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF;
    match framing {
        Framing::Raw => {}
        Framing::Zlib => flags |= TINFL_FLAG_PARSE_ZLIB_HEADER | TINFL_FLAG_COMPUTE_ADLER32,
        Framing::Gzip => return Outcome::Rejected,
    }
    let mut out = vec![0u8; CAP];
    let mut state = Box::<DecompressorOxide>::default();
    let (status, _read, written) = decompress(&mut state, input, &mut out, 0, flags);
    match status {
        TINFLStatus::Done => {
            // miniz_oxide skips its own Adler-32 check when built with `--cfg fuzzing`, which
            // cargo-fuzz sets, so the trailer is compared here for every build.
            if framing == Framing::Zlib && state.adler32() != state.adler32_header() {
                return Outcome::Rejected;
            }
            out.truncate(written);
            Outcome::Ok(out)
        }
        TINFLStatus::HasMoreOutput => Outcome::Capped,
        _ => Outcome::Rejected,
    }
}

const Z_OK: c_int = 0;
const Z_STREAM_END: c_int = 1;

/// The zlib-API surface shared by the C zlib and libz-rs-sys drivers.
trait ZApi: Sized {
    fn init(window_bits: c_int) -> Option<Self>;
    /// One `inflate(Z_NO_FLUSH)` call: (return code, input consumed, output produced).
    fn step(&mut self, input: &[u8], out: &mut [u8]) -> (c_int, usize, usize);
    fn reset(&mut self) -> c_int;
}

fn drive<Z: ZApi>(framing: Framing, input: &[u8]) -> Outcome {
    let bits = match framing {
        Framing::Raw => -15,
        Framing::Zlib => 15,
        Framing::Gzip => 31,
    };
    let Some(mut z) = Z::init(bits) else {
        return Outcome::Rejected;
    };
    let mut out = Vec::new();
    let mut buf = vec![0u8; 1 << 16];
    let mut pos = 0usize;
    loop {
        loop {
            let (rc, used, produced) = z.step(&input[pos..], &mut buf);
            pos += used;
            out.extend_from_slice(&buf[..produced]);
            if out.len() > CAP {
                return Outcome::Capped;
            }
            match rc {
                Z_STREAM_END => break,
                Z_OK if used > 0 || produced > 0 => {}
                _ => return Outcome::Rejected,
            }
        }
        if framing == Framing::Gzip && input[pos..].starts_with(&[0x1f, 0x8b]) {
            if z.reset() != Z_OK {
                return Outcome::Rejected;
            }
            continue;
        }
        return Outcome::Ok(out);
    }
}

#[repr(C)]
struct CStream {
    next_in: *const u8,
    avail_in: c_uint,
    total_in: c_ulong,
    next_out: *mut u8,
    avail_out: c_uint,
    total_out: c_ulong,
    msg: *const c_char,
    state: *mut c_void,
    zalloc: *const c_void,
    zfree: *const c_void,
    opaque: *mut c_void,
    data_type: c_int,
    adler: c_ulong,
    reserved: c_ulong,
}

extern "C" {
    fn zlibVersion() -> *const c_char;
    fn inflateInit2_(s: *mut CStream, bits: c_int, version: *const c_char, size: c_int) -> c_int;
    fn inflate(s: *mut CStream, flush: c_int) -> c_int;
    fn inflateReset(s: *mut CStream) -> c_int;
    fn inflateEnd(s: *mut CStream) -> c_int;
}

struct CZlib(Box<CStream>);

impl ZApi for CZlib {
    fn init(window_bits: c_int) -> Option<Self> {
        let mut s = Box::new(CStream {
            next_in: std::ptr::null(),
            avail_in: 0,
            total_in: 0,
            next_out: std::ptr::null_mut(),
            avail_out: 0,
            total_out: 0,
            msg: std::ptr::null(),
            state: std::ptr::null_mut(),
            zalloc: std::ptr::null(),
            zfree: std::ptr::null(),
            opaque: std::ptr::null_mut(),
            data_type: 0,
            adler: 0,
            reserved: 0,
        });
        let size = std::mem::size_of::<CStream>() as c_int;
        // SAFETY: `s` is a valid, zeroed-callback stream; zlib allocates its own state.
        let rc = unsafe { inflateInit2_(&mut *s, window_bits, zlibVersion(), size) };
        (rc == Z_OK).then_some(CZlib(s))
    }

    fn step(&mut self, input: &[u8], out: &mut [u8]) -> (c_int, usize, usize) {
        let s = &mut *self.0;
        s.next_in = input.as_ptr();
        s.avail_in = input.len() as c_uint;
        s.next_out = out.as_mut_ptr();
        s.avail_out = out.len() as c_uint;
        // SAFETY: the pointers and lengths describe live slices for the duration of the call.
        let rc = unsafe { inflate(s, 0) };
        (
            rc,
            input.len() - s.avail_in as usize,
            out.len() - s.avail_out as usize,
        )
    }

    fn reset(&mut self) -> c_int {
        // SAFETY: the stream was initialised by `inflateInit2_`.
        unsafe { inflateReset(&mut *self.0) }
    }
}

impl Drop for CZlib {
    fn drop(&mut self) {
        // SAFETY: the stream was initialised by `inflateInit2_` and is ended once.
        unsafe { inflateEnd(&mut *self.0) };
    }
}

struct Zrs(Box<libz_rs_sys::z_stream>);

impl ZApi for Zrs {
    fn init(window_bits: c_int) -> Option<Self> {
        let mut s = Box::new(libz_rs_sys::z_stream::default());
        let size = std::mem::size_of::<libz_rs_sys::z_stream>() as c_int;
        // SAFETY: a default stream is valid input for init, which allocates its own state.
        let rc = unsafe {
            libz_rs_sys::inflateInit2_(&mut *s, window_bits, libz_rs_sys::zlibVersion(), size)
        };
        (rc == Z_OK).then_some(Zrs(s))
    }

    fn step(&mut self, input: &[u8], out: &mut [u8]) -> (c_int, usize, usize) {
        let s = &mut *self.0;
        s.next_in = input.as_ptr();
        s.avail_in = input.len() as c_uint;
        s.next_out = out.as_mut_ptr();
        s.avail_out = out.len() as c_uint;
        // SAFETY: the pointers and lengths describe live slices for the duration of the call.
        let rc = unsafe { libz_rs_sys::inflate(s, 0) };
        (
            rc,
            input.len() - s.avail_in as usize,
            out.len() - s.avail_out as usize,
        )
    }

    fn reset(&mut self) -> c_int {
        // SAFETY: the stream was initialised by `inflateInit2_`.
        unsafe { libz_rs_sys::inflateReset(&mut *self.0) }
    }
}

impl Drop for Zrs {
    fn drop(&mut self) {
        // SAFETY: the stream was initialised by `inflateInit2_` and is ended once.
        unsafe { libz_rs_sys::inflateEnd(&mut *self.0) };
    }
}

/// Reference zlib 1.3.2 (build/c/zlib).
pub fn decode_zlib(framing: Framing, input: &[u8]) -> Outcome {
    drive::<CZlib>(framing, input)
}

/// libz-rs-sys 0.6.8.
pub fn decode_zrs(framing: Framing, input: &[u8]) -> Outcome {
    drive::<Zrs>(framing, input)
}

/// Which reference a target compares cf against.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reference {
    Zlib,
    Zrs,
    Mox,
}

/// Split an input into its framing and stream. mox targets choose raw or zlib (mod 2); the others
/// choose raw, zlib or gzip (mod 3).
pub fn split(reference: Reference, data: &[u8]) -> Option<(Framing, &[u8])> {
    let (first, rest) = data.split_first()?;
    let framing = if reference == Reference::Mox {
        [Framing::Raw, Framing::Zlib][usize::from(*first % 2)]
    } else {
        [Framing::Raw, Framing::Zlib, Framing::Gzip][usize::from(*first % 3)]
    };
    Some((framing, rest))
}

/// Run one differential check; the error names both outcomes.
pub fn check(reference: Reference, data: &[u8]) -> Result<(), String> {
    let Some((framing, input)) = split(reference, data) else {
        return Ok(());
    };
    let cf = decode_cf(framing, input);
    let other = match reference {
        Reference::Zlib => decode_zlib(framing, input),
        Reference::Zrs => decode_zrs(framing, input),
        Reference::Mox => decode_mox(framing, input),
    };
    compare(&cf, &other).map_err(|m| {
        format!(
            "{m} (cf vs {reference:?}, {framing:?}, {} input bytes)",
            input.len()
        )
    })
}
