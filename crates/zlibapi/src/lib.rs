//! zlib-API FFI shared by the C subjects (`zlib`, `zlib-nohw`, `zsys`).
//!
//! This crate carries no link directives; each binary's `build.rs` decides which
//! library provides the symbols.

use harness::alloc::{c_zalloc, c_zfree};
use harness::subject::ERR_OUTPUT_FULL;
use harness::{Caps, DecodeError, Framing, OutputLimit, StreamOutcome, Subject};
use std::ffi::{c_char, c_int, c_uint, c_ulong, c_void, CStr};
use std::marker::PhantomData;

pub const Z_OK: c_int = 0;
pub const Z_STREAM_END: c_int = 1;
pub const Z_NEED_DICT: c_int = 2;
pub const Z_STREAM_ERROR: c_int = -2;
pub const Z_DATA_ERROR: c_int = -3;
pub const Z_MEM_ERROR: c_int = -4;
pub const Z_BUF_ERROR: c_int = -5;
pub const Z_VERSION_ERROR: c_int = -6;
pub const Z_NO_FLUSH: c_int = 0;
pub const Z_FINISH: c_int = 4;
pub const Z_DEFLATED: c_int = 8;
pub const Z_DEFAULT_STRATEGY: c_int = 0;

pub type AllocFunc = unsafe extern "C" fn(*mut c_void, c_uint, c_uint) -> *mut c_void;
pub type FreeFunc = unsafe extern "C" fn(*mut c_void, *mut c_void);

#[repr(C)]
pub struct ZStream {
    pub next_in: *const u8,
    pub avail_in: c_uint,
    pub total_in: c_ulong,
    pub next_out: *mut u8,
    pub avail_out: c_uint,
    pub total_out: c_ulong,
    pub msg: *const c_char,
    pub state: *mut c_void,
    pub zalloc: Option<AllocFunc>,
    pub zfree: Option<FreeFunc>,
    pub opaque: *mut c_void,
    pub data_type: c_int,
    pub adler: c_ulong,
    pub reserved: c_ulong,
}

#[repr(C)]
pub struct GzHeader {
    pub text: c_int,
    pub time: c_ulong,
    pub xflags: c_int,
    pub os: c_int,
    pub extra: *mut u8,
    pub extra_len: c_uint,
    pub extra_max: c_uint,
    pub name: *mut u8,
    pub name_max: c_uint,
    pub comment: *mut u8,
    pub comm_max: c_uint,
    pub hcrc: c_int,
    pub done: c_int,
}

extern "C" {
    pub fn zlibVersion() -> *const c_char;
    pub fn inflateInit2_(
        strm: *mut ZStream,
        window_bits: c_int,
        version: *const c_char,
        stream_size: c_int,
    ) -> c_int;
    pub fn inflate(strm: *mut ZStream, flush: c_int) -> c_int;
    pub fn inflateEnd(strm: *mut ZStream) -> c_int;
    pub fn inflateSetDictionary(strm: *mut ZStream, dict: *const u8, len: c_uint) -> c_int;
    pub fn deflateInit2_(
        strm: *mut ZStream,
        level: c_int,
        method: c_int,
        window_bits: c_int,
        mem_level: c_int,
        strategy: c_int,
        version: *const c_char,
        stream_size: c_int,
    ) -> c_int;
    pub fn deflate(strm: *mut ZStream, flush: c_int) -> c_int;
    pub fn deflateEnd(strm: *mut ZStream) -> c_int;
    pub fn deflateSetHeader(strm: *mut ZStream, head: *mut GzHeader) -> c_int;
    pub fn adler32(adler: c_ulong, buf: *const u8, len: c_uint) -> c_ulong;
    pub fn crc32(crc: c_ulong, buf: *const u8, len: c_uint) -> c_ulong;
}

/// Identifies one zlib-API provider.
pub trait Variant {
    const ID: &'static str;
    /// Only the stock zlib subject compresses.
    const COMPRESS: bool;
}

/// A `Subject` over the zlib API, parameterised by which library is linked.
pub struct Api<V: Variant>(PhantomData<V>);

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

fn blank_stream() -> Box<ZStream> {
    Box::new(ZStream {
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

fn zerr(strm: &ZStream, rc: c_int) -> DecodeError {
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
    strm: Box<ZStream>,
}

impl Drop for Inflater {
    fn drop(&mut self) {
        unsafe { inflateEnd(&mut *self.strm) };
    }
}

impl Inflater {
    fn new(f: Framing, dict: Option<&[u8]>) -> Result<Inflater, DecodeError> {
        let mut strm = blank_stream();
        let rc = unsafe {
            inflateInit2_(
                &mut *strm,
                window_bits(f),
                zlibVersion(),
                std::mem::size_of::<ZStream>() as c_int,
            )
        };
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
        let rc = unsafe { inflateSetDictionary(&mut *self.strm, d.as_ptr(), d.len() as c_uint) };
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
            let rc = unsafe { inflate(&mut *self.strm, flush) };
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

fn deflate_all(level: i32, f: Framing, input: &[u8]) -> Result<Vec<u8>, DecodeError> {
    let mut strm = blank_stream();
    let rc = unsafe {
        deflateInit2_(
            &mut *strm,
            level,
            Z_DEFLATED,
            window_bits(f),
            8,
            Z_DEFAULT_STRATEGY,
            zlibVersion(),
            std::mem::size_of::<ZStream>() as c_int,
        )
    };
    if rc != Z_OK {
        return Err(zerr(&strm, rc));
    }
    if f == Framing::Gzip {
        let mut head = GzHeader {
            text: 0,
            time: 0,
            xflags: 0,
            os: 255,
            extra: std::ptr::null_mut(),
            extra_len: 0,
            extra_max: 0,
            name: std::ptr::null_mut(),
            name_max: 0,
            comment: std::ptr::null_mut(),
            comm_max: 0,
            hcrc: 0,
            done: 0,
        };
        let rc = unsafe { deflateSetHeader(&mut *strm, &mut head) };
        if rc != Z_OK {
            unsafe { deflateEnd(&mut *strm) };
            return Err(zerr(&strm, rc));
        }
        // deflateSetHeader keeps a pointer to `head` only until the header is written, which
        // happens during the first deflate call below, while `head` is still alive.
        return finish_deflate(strm, input, Some(head));
    }
    finish_deflate(strm, input, None)
}

fn finish_deflate(
    mut strm: Box<ZStream>,
    input: &[u8],
    _head: Option<GzHeader>,
) -> Result<Vec<u8>, DecodeError> {
    let mut out: Vec<u8> = Vec::with_capacity(input.len() / 2 + 64);
    let mut buf = vec![0u8; 1 << 16];
    strm.next_in = input.as_ptr();
    strm.avail_in = input.len() as c_uint;
    let result = loop {
        strm.next_out = buf.as_mut_ptr();
        strm.avail_out = buf.len() as c_uint;
        let rc = unsafe { deflate(&mut *strm, Z_FINISH) };
        let n = buf.len() - strm.avail_out as usize;
        out.extend_from_slice(&buf[..n]);
        match rc {
            Z_STREAM_END => break Ok(out),
            Z_OK | Z_BUF_ERROR => continue,
            other => break Err(zerr(&strm, other)),
        }
    };
    unsafe { deflateEnd(&mut *strm) };
    result
}

impl<V: Variant> Subject for Api<V> {
    fn id() -> &'static str {
        V::ID
    }

    fn impl_version() -> String {
        let v = unsafe { CStr::from_ptr(zlibVersion()) };
        v.to_string_lossy().into_owned()
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
    ) -> Result<usize, DecodeError> {
        let mut inf = Inflater::new(f, dict)?;
        inf.strm.next_in = input.as_ptr();
        inf.strm.avail_in = input.len() as c_uint;
        inf.strm.next_out = out.as_mut_ptr();
        inf.strm.avail_out = out.len() as c_uint;
        let rc = inf.step(Z_FINISH, dict)?;
        match rc {
            Z_STREAM_END => Ok(inf.strm.total_out as usize),
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
            inf.strm.avail_in = chunk.len() as c_uint;
            loop {
                inf.strm.next_out = out_buf.as_mut_ptr();
                inf.strm.avail_out = out_buf.len() as c_uint;
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
        let consumed: u64 = inf.strm.total_in;
        Ok(StreamOutcome {
            produced,
            consumed,
            limit_hit: false,
            trailing_bytes: input.len() as u64 - consumed,
        })
    }

    fn adler32(data: &[u8]) -> Option<u32> {
        Some(unsafe { adler32(1, data.as_ptr(), data.len() as c_uint) } as u32)
    }

    fn crc32(data: &[u8]) -> Option<u32> {
        Some(unsafe { crc32(0, data.as_ptr(), data.len() as c_uint) } as u32)
    }

    fn compress(level: i32, f: Framing, input: &[u8]) -> Option<Result<Vec<u8>, DecodeError>> {
        if V::COMPRESS {
            Some(deflate_all(level, f, input))
        } else {
            None
        }
    }
}
