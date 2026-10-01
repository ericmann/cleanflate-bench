//! `cfb-mox`: miniz_oxide behind the harness `Subject` trait.

use harness::subject::{OneshotOutcome, ERR_OUTPUT_FULL};
use harness::{Caps, DecodeError, Framing, OutputLimit, StreamOutcome, Subject};
use miniz_oxide::inflate::core::inflate_flags::{
    TINFL_FLAG_COMPUTE_ADLER32, TINFL_FLAG_PARSE_ZLIB_HEADER,
    TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF,
};
use miniz_oxide::inflate::core::{decompress, DecompressorOxide};
use miniz_oxide::inflate::stream::{inflate, InflateState};
use miniz_oxide::inflate::TINFLStatus;
use miniz_oxide::{DataFormat, MZError, MZFlush, MZStatus};

struct Mox;

fn unsupported(f: Framing) -> Result<(), DecodeError> {
    match f {
        Framing::Gzip => Err(DecodeError::new(
            "unsupported",
            "miniz_oxide has no gzip framing",
        )),
        _ => Ok(()),
    }
}

impl Subject for Mox {
    fn id() -> &'static str {
        "mox"
    }

    fn impl_version() -> String {
        "miniz_oxide 0.9.1".to_string()
    }

    fn caps() -> Caps {
        Caps {
            framings: vec![Framing::Raw, Framing::Zlib],
            oneshot: true,
            stream: true,
            adler32: true,
            crc32: false,
            dictionary: false,
            output_limit: OutputLimit::Caller,
        }
    }

    fn oneshot(
        f: Framing,
        input: &[u8],
        out: &mut [u8],
        dict: Option<&[u8]>,
    ) -> Result<OneshotOutcome, DecodeError> {
        unsupported(f)?;
        if dict.is_some() {
            return Err(DecodeError::new("unsupported", "no dictionary support"));
        }
        let mut flags = TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF;
        if f == Framing::Zlib {
            flags |= TINFL_FLAG_PARSE_ZLIB_HEADER | TINFL_FLAG_COMPUTE_ADLER32;
        }
        let mut r = DecompressorOxide::new();
        let (status, read, written) = decompress(&mut r, input, out, 0, flags);
        match status {
            TINFLStatus::Done => Ok(OneshotOutcome {
                produced: written,
                consumed: read,
            }),
            TINFLStatus::HasMoreOutput => {
                Err(DecodeError::new(ERR_OUTPUT_FULL, "buffer too small"))
            }
            other => Err(DecodeError::new(
                &format!("{other:?}"),
                format!("{other:?}"),
            )),
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
        unsupported(f)?;
        if dict.is_some() {
            return Err(DecodeError::new("unsupported", "no dictionary support"));
        }
        let format = if f == Framing::Zlib {
            DataFormat::Zlib
        } else {
            DataFormat::Raw
        };
        let mut state = InflateState::new_boxed(format);
        let mut produced = 0u64;
        let mut consumed = 0u64;
        let mut done = false;
        'outer: for chunk in input.chunks(in_chunk.max(1)) {
            let mut rest = chunk;
            loop {
                let r = inflate(&mut state, rest, out_buf, MZFlush::None);
                if r.bytes_written > 0 {
                    sink(&out_buf[..r.bytes_written]);
                    produced += r.bytes_written as u64;
                }
                rest = &rest[r.bytes_consumed..];
                consumed += r.bytes_consumed as u64;
                match r.status {
                    Ok(MZStatus::StreamEnd) => {
                        done = true;
                        break 'outer;
                    }
                    Ok(_) => {
                        if r.bytes_consumed == 0 && r.bytes_written == 0 {
                            break;
                        }
                    }
                    // No progress possible without more input.
                    Err(MZError::Buf) => break,
                    Err(e) => return Err(DecodeError::new(&format!("{e:?}"), format!("{e:?}"))),
                }
            }
        }
        if !done {
            return Err(DecodeError::new(
                "Truncated",
                "input ended before end of stream",
            ));
        }
        Ok(StreamOutcome {
            produced,
            consumed,
            limit_hit: false,
            trailing_bytes: input.len() as u64 - consumed,
        })
    }

    fn adler32(data: &[u8]) -> Option<u32> {
        Some(miniz_oxide::mz_adler32_oxide(
            miniz_oxide::MZ_ADLER32_INIT,
            data,
        ))
    }

    fn crc32(_data: &[u8]) -> Option<u32> {
        None
    }

    fn compress(_l: i32, _f: Framing, _i: &[u8]) -> Option<Result<Vec<u8>, DecodeError>> {
        None
    }
}

fn main() {
    harness::cli::run_main::<Mox>()
}
