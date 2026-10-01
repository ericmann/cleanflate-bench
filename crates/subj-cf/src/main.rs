//! `cfb-cf`: cleanflate (pinned by SHA) behind the harness `Subject` trait.
//!
//! Exactly one of the features `round1`, `round2` and `round3` (default) selects which cleanflate
//! release round is linked; the three revisions come from `config/rounds.json`.

#[cfg(any(
    all(feature = "round1", feature = "round2"),
    all(feature = "round1", feature = "round3"),
    all(feature = "round2", feature = "round3"),
    not(any(feature = "round1", feature = "round2", feature = "round3"))
))]
compile_error!("enable exactly one of the features round1, round2 and round3");

#[cfg(feature = "round1")]
use cleanflate_r1 as cleanflate;
#[cfg(feature = "round2")]
use cleanflate_r2 as cleanflate;
#[cfg(feature = "round3")]
use cleanflate_r3 as cleanflate;

#[cfg(feature = "round1")]
const ROUND: &str = "round 1 @e94efcf";
#[cfg(feature = "round2")]
const ROUND: &str = "round 2 @d3e911b";
#[cfg(feature = "round3")]
const ROUND: &str = "round 3 @85f2100";

use cleanflate::{Decompressor, Error, Format, Options, Status};
use harness::subject::{OneshotOutcome, ERR_OUTPUT_FULL};
use harness::{Caps, DecodeError, Framing, OutputLimit, StreamOutcome, Subject};

struct Cf;

fn fmt(f: Framing) -> Format {
    match f {
        Framing::Raw => Format::Raw,
        Framing::Zlib => Format::Zlib,
        Framing::Gzip => Format::Gzip,
    }
}

fn err(e: Error) -> DecodeError {
    DecodeError::new(e.kind().as_str(), e.to_string())
}

/// cf's default output cap would interfere with perf runs, so the limit is lifted unless the
/// caller asks for one.
fn options(max_output: Option<u64>, dict: Option<&[u8]>) -> Options {
    Options {
        max_output: max_output.unwrap_or(u64::MAX),
        dictionary: dict.map(|d| d.to_vec()),
        ..Options::default()
    }
}

impl Subject for Cf {
    fn id() -> &'static str {
        "cf"
    }

    fn impl_version() -> String {
        format!("cleanflate 0.1.0 {ROUND}")
    }

    fn caps() -> Caps {
        Caps {
            framings: vec![Framing::Raw, Framing::Zlib, Framing::Gzip],
            oneshot: true,
            stream: true,
            adler32: true,
            crc32: true,
            dictionary: true,
            output_limit: OutputLimit::Native,
        }
    }

    fn oneshot(
        f: Framing,
        input: &[u8],
        out: &mut [u8],
        dict: Option<&[u8]>,
    ) -> Result<OneshotOutcome, DecodeError> {
        let mut d = Decompressor::new(fmt(f), options(None, dict));
        let mut inp = input;
        let mut pos = 0usize;
        let mut probe = [0u8; 1];
        loop {
            let p = d.decompress(inp, &mut out[pos..]).map_err(err)?;
            inp = &inp[p.consumed..];
            pos += p.produced;
            match p.status {
                Status::Done => break,
                Status::NeedsInput => {
                    // Gzip cannot report Done until it knows no further member follows;
                    // `finish` resolves that (and fails with Truncated if input ended early).
                    d.finish().map_err(err)?;
                    break;
                }
                Status::OutputFull => {
                    if pos == out.len() {
                        // The buffer may be exactly full with only the trailer left to read.
                        let q = d.decompress(inp, &mut probe).map_err(err)?;
                        if q.produced > 0 || q.status != Status::Done {
                            return Err(DecodeError::new(ERR_OUTPUT_FULL, "buffer too small"));
                        }
                        inp = &inp[q.consumed..];
                        break;
                    }
                    if p.consumed == 0 && p.produced == 0 {
                        return Err(DecodeError::new(ERR_OUTPUT_FULL, "no progress"));
                    }
                }
            }
        }
        if !inp.is_empty() {
            // Default options reject trailing data; surface exactly that.
            d.decompress(inp, &mut probe).map_err(err)?;
        }
        d.finish().map_err(err)?;
        Ok(OneshotOutcome {
            produced: pos,
            consumed: input.len() - inp.len(),
        })
    }

    fn stream(
        f: Framing,
        input: &[u8],
        in_chunk: usize,
        out_buf: &mut [u8],
        sink: &mut dyn FnMut(&[u8]),
        max_output: Option<u64>,
        dict: Option<&[u8]>,
    ) -> Result<StreamOutcome, DecodeError> {
        let mut d = Decompressor::new(fmt(f), options(max_output, dict));
        let mut produced = 0u64;
        let mut consumed = 0u64;
        for chunk in input.chunks(in_chunk.max(1)) {
            let mut rest = chunk;
            loop {
                let p = match d.decompress(rest, out_buf) {
                    Ok(p) => p,
                    Err(Error::OutputLimitExceeded { .. }) => {
                        return Ok(StreamOutcome {
                            produced,
                            consumed,
                            limit_hit: true,
                            trailing_bytes: 0,
                        });
                    }
                    Err(e) => return Err(err(e)),
                };
                if p.produced > 0 {
                    sink(&out_buf[..p.produced]);
                    produced += p.produced as u64;
                }
                rest = &rest[p.consumed..];
                consumed += p.consumed as u64;
                let stalled = p.consumed == 0 && p.produced == 0;
                match p.status {
                    Status::NeedsInput => break,
                    Status::OutputFull => {
                        if stalled {
                            break;
                        }
                    }
                    Status::Done => {
                        if rest.is_empty() || stalled {
                            break;
                        }
                    }
                }
            }
        }
        d.finish().map_err(err)?;
        Ok(StreamOutcome {
            produced,
            consumed,
            limit_hit: false,
            trailing_bytes: 0,
        })
    }

    fn adler32(data: &[u8]) -> Option<u32> {
        Some(cleanflate::checksum::adler32(data))
    }

    fn crc32(data: &[u8]) -> Option<u32> {
        Some(cleanflate::checksum::crc32(data))
    }

    fn compress(_l: i32, _f: Framing, _i: &[u8]) -> Option<Result<Vec<u8>, DecodeError>> {
        None
    }
}

fn main() {
    harness::cli::run_main::<Cf>()
}
