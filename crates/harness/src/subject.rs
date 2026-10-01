//! The interface every benchmarked implementation provides.

use crate::Framing;

/// Error kind a subject returns when the one-shot output buffer is too small.
pub const ERR_OUTPUT_FULL: &str = "output_full";
/// Error kind for an operation the subject does not support.
pub const ERR_UNSUPPORTED: &str = "unsupported";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OutputLimit {
    /// The subject enforces an output limit itself.
    Native,
    /// The caller must count output and stop.
    Caller,
}

impl OutputLimit {
    pub fn as_str(self) -> &'static str {
        match self {
            OutputLimit::Native => "native",
            OutputLimit::Caller => "caller",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Caps {
    pub framings: Vec<Framing>,
    pub oneshot: bool,
    pub stream: bool,
    pub adler32: bool,
    pub crc32: bool,
    pub dictionary: bool,
    pub output_limit: OutputLimit,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct StreamOutcome {
    pub produced: u64,
    pub consumed: u64,
    pub limit_hit: bool,
    pub trailing_bytes: u64,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct OneshotOutcome {
    pub produced: usize,
    pub consumed: usize,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DecodeError {
    pub kind: String,
    pub message: String,
}

impl DecodeError {
    pub fn new(kind: &str, message: impl Into<String>) -> DecodeError {
        DecodeError {
            kind: kind.to_string(),
            message: message.into(),
        }
    }
}

impl std::fmt::Display for DecodeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.kind, self.message)
    }
}

impl std::error::Error for DecodeError {}

/// A decompression implementation. Every call builds a fresh decoder.
pub trait Subject {
    fn id() -> &'static str;
    fn impl_version() -> String;
    fn caps() -> Caps;

    /// Decode all of `input` into `out`, returning the bytes written and the input bytes consumed.
    fn oneshot(
        f: Framing,
        input: &[u8],
        out: &mut [u8],
        dict: Option<&[u8]>,
    ) -> Result<OneshotOutcome, DecodeError>;

    /// Decode `input` fed in `in_chunk`-sized pieces through `out_buf`, passing every
    /// produced slice to `sink`.
    #[allow(clippy::too_many_arguments)]
    fn stream(
        f: Framing,
        input: &[u8],
        in_chunk: usize,
        out_buf: &mut [u8],
        sink: &mut dyn FnMut(&[u8]),
        max_output: Option<u64>,
        dict: Option<&[u8]>,
    ) -> Result<StreamOutcome, DecodeError>;

    fn adler32(data: &[u8]) -> Option<u32>;
    fn crc32(data: &[u8]) -> Option<u32>;

    /// `None` unless the subject can compress.
    fn compress(level: i32, f: Framing, input: &[u8]) -> Option<Result<Vec<u8>, DecodeError>>;
}
