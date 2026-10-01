//! `cfb-zrs`: zlib-rs (via libz-rs-sys's zlib-style API) behind the harness `Subject` trait.

use harness::subject::{OneshotOutcome, ERR_OUTPUT_FULL};
use harness::{Caps, DecodeError, Framing, OutputLimit, StreamOutcome, Subject};
use libz_rs_sys as z;
use std::ffi::{c_int, CStr};

struct Zrs;

struct Inflater {
    strm: Box<z::z_stream>,
}

impl Drop for Inflater {
    fn drop(&mut self) {
        unsafe { z::inflateEnd(&mut *self.strm) };
    }
}

fn code_name(rc: c_int) -> &'static str {
    match rc {
        z::Z_OK => "Z_OK",
        z::Z_STREAM_END => "Z_STREAM_END",
        z::Z_NEED_DICT => "Z_NEED_DICT",
        z::Z_ERRNO => "Z_ERRNO",
        z::Z_STREAM_ERROR => "Z_STREAM_ERROR",
        z::Z_DATA_ERROR => "Z_DATA_ERROR",
        z::Z_MEM_ERROR => "Z_MEM_ERROR",
        z::Z_BUF_ERROR => "Z_BUF_ERROR",
        z::Z_VERSION_ERROR => "Z_VERSION_ERROR",
        _ => "Z_UNKNOWN",
    }
}

fn zerr(inf: &Inflater, rc: c_int) -> DecodeError {
    let msg = if inf.strm.msg.is_null() {
        String::new()
    } else {
        unsafe { CStr::from_ptr(inf.strm.msg) }
            .to_string_lossy()
            .into_owned()
    };
    DecodeError::new(code_name(rc), msg)
}

impl Inflater {
    fn new(f: Framing, dict: Option<&[u8]>) -> Result<Inflater, DecodeError> {
        let window_bits = match f {
            Framing::Raw => -15,
            Framing::Zlib => 15,
            Framing::Gzip => 31,
        };
        let mut strm = Box::new(z::z_stream::default());
        let rc = unsafe {
            z::inflateInit2_(
                &mut *strm,
                window_bits,
                z::zlibVersion(),
                std::mem::size_of::<z::z_stream>() as c_int,
            )
        };
        let mut inf = Inflater { strm };
        if rc != z::Z_OK {
            return Err(zerr(&inf, rc));
        }
        if f == Framing::Raw {
            if let Some(d) = dict {
                inf.set_dictionary(d)?;
            }
        }
        Ok(inf)
    }

    fn set_dictionary(&mut self, d: &[u8]) -> Result<(), DecodeError> {
        let rc = unsafe { z::inflateSetDictionary(&mut *self.strm, d.as_ptr(), d.len() as u32) };
        if rc == z::Z_OK {
            Ok(())
        } else {
            Err(zerr(self, rc))
        }
    }

    /// One `inflate` call, answering `Z_NEED_DICT` from `dict` when possible.
    fn step(&mut self, flush: c_int, dict: Option<&[u8]>) -> Result<c_int, DecodeError> {
        let mut tried = false;
        loop {
            let rc = unsafe { z::inflate(&mut *self.strm, flush) };
            if rc == z::Z_NEED_DICT && !tried {
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

impl Subject for Zrs {
    fn id() -> &'static str {
        "zrs"
    }

    fn impl_version() -> String {
        let v = unsafe { CStr::from_ptr(z::zlibVersion()) }.to_string_lossy();
        format!("libz-rs-sys 0.6.8 ({v})")
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
        inf.strm.next_in = input.as_ptr() as *mut u8;
        inf.strm.avail_in = input.len() as u32;
        inf.strm.next_out = out.as_mut_ptr();
        inf.strm.avail_out = out.len() as u32;
        let rc = inf.step(z::Z_FINISH, dict)?;
        match rc {
            z::Z_STREAM_END => Ok(OneshotOutcome {
                produced: inf.strm.total_out as usize,
                consumed: inf.strm.total_in as usize,
            }),
            z::Z_OK | z::Z_BUF_ERROR if inf.strm.avail_out == 0 => {
                Err(DecodeError::new(ERR_OUTPUT_FULL, "buffer too small"))
            }
            z::Z_OK | z::Z_BUF_ERROR => Err(DecodeError::new("Z_BUF_ERROR", "truncated input")),
            other => Err(zerr(&inf, other)),
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
            inf.strm.next_in = chunk.as_ptr() as *mut u8;
            inf.strm.avail_in = chunk.len() as u32;
            loop {
                inf.strm.next_out = out_buf.as_mut_ptr();
                inf.strm.avail_out = out_buf.len() as u32;
                let rc = inf.step(z::Z_NO_FLUSH, dict)?;
                let n = out_buf.len() - inf.strm.avail_out as usize;
                if n > 0 {
                    sink(&out_buf[..n]);
                    produced += n as u64;
                }
                match rc {
                    z::Z_STREAM_END => {
                        done = true;
                        break 'outer;
                    }
                    z::Z_OK => {
                        if inf.strm.avail_in == 0 && inf.strm.avail_out != 0 {
                            break;
                        }
                    }
                    // No progress possible without more input.
                    z::Z_BUF_ERROR => break,
                    other => return Err(zerr(&inf, other)),
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
        Some(unsafe { z::adler32(1, data.as_ptr(), data.len() as u32) } as u32)
    }

    fn crc32(data: &[u8]) -> Option<u32> {
        Some(unsafe { z::crc32(0, data.as_ptr(), data.len() as u32) } as u32)
    }

    fn compress(_l: i32, _f: Framing, _i: &[u8]) -> Option<Result<Vec<u8>, DecodeError>> {
        None
    }
}

fn main() {
    harness::cli::run_main::<Zrs>()
}
