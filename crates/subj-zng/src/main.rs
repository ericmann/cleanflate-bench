//! `cfb-zng`: zlib-ng 2.3.3 through its native `zng_` API (not compat mode).

use harness::alloc::{c_zalloc, c_zfree};
use harness::subject::{OneshotOutcome, ERR_OUTPUT_FULL};
use harness::{Caps, DecodeError, Framing, OutputLimit, StreamOutcome, Subject};
use std::ffi::{c_char, c_int, c_uint, c_ulong, c_void, CStr};

const Z_OK: i32 = 0;
const Z_STREAM_END: i32 = 1;
const Z_NEED_DICT: i32 = 2;
const Z_STREAM_ERROR: i32 = -2;
const Z_DATA_ERROR: i32 = -3;
const Z_MEM_ERROR: i32 = -4;
const Z_BUF_ERROR: i32 = -5;
const Z_VERSION_ERROR: i32 = -6;
const Z_NO_FLUSH: i32 = 0;
const Z_FINISH: i32 = 4;

type AllocFunc = unsafe extern "C" fn(*mut c_void, c_uint, c_uint) -> *mut c_void;
type FreeFunc = unsafe extern "C" fn(*mut c_void, *mut c_void);

/// Mirrors `zng_stream` from the generated `build/c/zng/include/zlib-ng.h`.
#[repr(C)]
pub struct ZngStream {
    next_in: *const u8,
    avail_in: u32,
    total_in: usize,
    next_out: *mut u8,
    avail_out: u32,
    total_out: usize,
    msg: *const c_char,
    state: *mut c_void,
    zalloc: Option<AllocFunc>,
    zfree: Option<FreeFunc>,
    opaque: *mut c_void,
    data_type: c_int,
    adler: u32,
    reserved: c_ulong,
}

extern "C" {
    fn zlibng_version() -> *const c_char;
    fn zng_inflateInit2(strm: *mut ZngStream, window_bits: i32) -> i32;
    fn zng_inflate(strm: *mut ZngStream, flush: i32) -> i32;
    fn zng_inflateEnd(strm: *mut ZngStream) -> i32;
    fn zng_inflateSetDictionary(strm: *mut ZngStream, dict: *const u8, len: u32) -> i32;
    fn zng_adler32(adler: u32, buf: *const u8, len: u32) -> u32;
    fn zng_crc32(crc: u32, buf: *const u8, len: u32) -> u32;
}

struct Zng;

fn code_name(rc: c_int) -> &'static str {
    match rc {
        Z_OK => "Z_OK",
        Z_STREAM_END => "Z_STREAM_END",
        Z_NEED_DICT => "Z_NEED_DICT",
        Z_STREAM_ERROR => "Z_STREAM_ERROR",
        Z_DATA_ERROR => "Z_DATA_ERROR",
        Z_MEM_ERROR => "Z_MEM_ERROR",
        Z_BUF_ERROR => "Z_BUF_ERROR",
        Z_VERSION_ERROR => "Z_VERSION_ERROR",
        _ => "Z_UNKNOWN",
    }
}

fn window_bits(f: Framing) -> c_int {
    match f {
        Framing::Raw => -15,
        Framing::Zlib => 15,
        Framing::Gzip => 31,
    }
}

fn blank_stream() -> Box<ZngStream> {
    Box::new(ZngStream {
        next_in: std::ptr::null(),
        avail_in: 0,
        total_in: 0,
        next_out: std::ptr::null_mut(),
        avail_out: 0,
        total_out: 0,
        msg: std::ptr::null(),
        state: std::ptr::null_mut(),
        zalloc: Some(c_zalloc),
        zfree: Some(c_zfree),
        opaque: std::ptr::null_mut(),
        data_type: 0,
        adler: 0,
        reserved: 0,
    })
}

fn zerr(strm: &ZngStream, rc: c_int) -> DecodeError {
    let msg = if strm.msg.is_null() {
        String::new()
    } else {
        unsafe { CStr::from_ptr(strm.msg) }
            .to_string_lossy()
            .into_owned()
    };
    DecodeError::new(code_name(rc), msg)
}

struct Inflater {
    strm: Box<ZngStream>,
}

impl Drop for Inflater {
    fn drop(&mut self) {
        unsafe { zng_inflateEnd(&mut *self.strm) };
    }
}

impl Inflater {
    fn new(f: Framing, dict: Option<&[u8]>) -> Result<Inflater, DecodeError> {
        let mut strm = blank_stream();
        let rc = unsafe { zng_inflateInit2(&mut *strm, window_bits(f)) };
        let mut inf = Inflater { strm };
        if rc != Z_OK {
            return Err(zerr(&inf.strm, rc));
        }
        if f == Framing::Raw {
            if let Some(d) = dict {
                inf.set_dictionary(d)?;
            }
        }
        Ok(inf)
    }

    fn set_dictionary(&mut self, d: &[u8]) -> Result<(), DecodeError> {
        let rc =
            unsafe { zng_inflateSetDictionary(&mut *self.strm, d.as_ptr(), d.len() as c_uint) };
        if rc == Z_OK {
            Ok(())
        } else {
            Err(zerr(&self.strm, rc))
        }
    }

    /// One `inflate` call, answering `Z_NEED_DICT` from `dict` when possible.
    fn step(&mut self, flush: c_int, dict: Option<&[u8]>) -> Result<c_int, DecodeError> {
        let mut tried = false;
        loop {
            let rc = unsafe { zng_inflate(&mut *self.strm, flush) };
            if rc == Z_NEED_DICT && !tried {
                if let Some(d) = dict {
                    tried = true;
                    self.set_dictionary(d)?;
                    continue;
                }
            }
            return Ok(rc);
        }
    }
}

impl Subject for Zng {
    fn id() -> &'static str {
        "zng"
    }

    fn impl_version() -> String {
        unsafe { CStr::from_ptr(zlibng_version()) }
            .to_string_lossy()
            .into_owned()
    }

    fn caps() -> Caps {
        Caps {
            framings: vec![Framing::Raw, Framing::Zlib, Framing::Gzip],
            oneshot: true,
            stream: true,
            adler32: true,
            crc32: true,
            dictionary: true,
            output_limit: OutputLimit::Caller,
        }
    }

    fn oneshot(
        f: Framing,
        input: &[u8],
        out: &mut [u8],
        dict: Option<&[u8]>,
    ) -> Result<OneshotOutcome, DecodeError> {
        let mut inf = Inflater::new(f, dict)?;
        inf.strm.next_in = input.as_ptr();
        inf.strm.avail_in = input.len() as u32;
        inf.strm.next_out = out.as_mut_ptr();
        inf.strm.avail_out = out.len() as u32;
        let rc = inf.step(Z_FINISH, dict)?;
        match rc {
            Z_STREAM_END => Ok(OneshotOutcome {
                produced: inf.strm.total_out,
                consumed: inf.strm.total_in,
            }),
            Z_OK | Z_BUF_ERROR if inf.strm.avail_out == 0 => {
                Err(DecodeError::new(ERR_OUTPUT_FULL, "buffer too small"))
            }
            Z_OK | Z_BUF_ERROR => Err(DecodeError::new("Z_BUF_ERROR", "truncated input")),
            other => Err(zerr(&inf.strm, other)),
        }
    }

    fn stream(
        f: Framing,
        input: &[u8],
        in_chunk: usize,
        out_buf: &mut [u8],
        sink: &mut dyn FnMut(&[u8]),
        _max_output: Option<u64>,
        dict: Option<&[u8]>,
    ) -> Result<StreamOutcome, DecodeError> {
        let mut inf = Inflater::new(f, dict)?;
        let mut produced = 0u64;
        let mut done = false;
        'outer: for chunk in input.chunks(in_chunk.max(1)) {
            inf.strm.next_in = chunk.as_ptr();
            inf.strm.avail_in = chunk.len() as u32;
            loop {
                inf.strm.next_out = out_buf.as_mut_ptr();
                inf.strm.avail_out = out_buf.len() as u32;
                let rc = inf.step(Z_NO_FLUSH, dict)?;
                let n = out_buf.len() - inf.strm.avail_out as usize;
                if n > 0 {
                    sink(&out_buf[..n]);
                    produced += n as u64;
                }
                match rc {
                    Z_STREAM_END => {
                        done = true;
                        break 'outer;
                    }
                    Z_OK => {
                        if inf.strm.avail_in == 0 && inf.strm.avail_out != 0 {
                            break;
                        }
                    }
                    // No progress possible without more input.
                    Z_BUF_ERROR => break,
                    other => return Err(zerr(&inf.strm, other)),
                }
            }
        }
        if !done {
            return Err(DecodeError::new(
                "Z_BUF_ERROR",
                "input ended before end of stream",
            ));
        }
        let consumed = inf.strm.total_in as u64;
        Ok(StreamOutcome {
            produced,
            consumed,
            limit_hit: false,
            trailing_bytes: input.len() as u64 - consumed,
        })
    }

    fn adler32(data: &[u8]) -> Option<u32> {
        Some(unsafe { zng_adler32(1, data.as_ptr(), data.len() as u32) })
    }

    fn crc32(data: &[u8]) -> Option<u32> {
        Some(unsafe { zng_crc32(0, data.as_ptr(), data.len() as u32) })
    }

    fn compress(_l: i32, _f: Framing, _i: &[u8]) -> Option<Result<Vec<u8>, DecodeError>> {
        None
    }
}

fn main() {
    harness::cli::run_main::<Zng>()
}

#[cfg(test)]
mod tests {
    use super::ZngStream;
    use std::mem::{offset_of, size_of};

    #[test]
    fn zng_stream_layout_matches_header() {
        // sizeof, then offsetof for each field in declaration order, printed by a C probe that
        // build.rs compiles against the generated zlib-ng.h.
        let got: Vec<usize> = env!("ZNG_STREAM_LAYOUT")
            .split(',')
            .map(|s| s.parse().unwrap())
            .collect();
        let want = vec![
            size_of::<ZngStream>(),
            offset_of!(ZngStream, next_in),
            offset_of!(ZngStream, avail_in),
            offset_of!(ZngStream, total_in),
            offset_of!(ZngStream, next_out),
            offset_of!(ZngStream, avail_out),
            offset_of!(ZngStream, total_out),
            offset_of!(ZngStream, msg),
            offset_of!(ZngStream, state),
            offset_of!(ZngStream, zalloc),
            offset_of!(ZngStream, zfree),
            offset_of!(ZngStream, opaque),
            offset_of!(ZngStream, data_type),
            offset_of!(ZngStream, adler),
            offset_of!(ZngStream, reserved),
        ];
        assert_eq!(got, want);
    }
}
