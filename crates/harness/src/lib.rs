//! Benchmark harness shared by every subject binary.

pub mod alloc;
pub mod cli;
pub mod subject;
pub mod timing;

/// Stream framing around a deflate payload.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Framing {
    Raw,
    Zlib,
    Gzip,
}

impl Framing {
    pub fn as_str(self) -> &'static str {
        match self {
            Framing::Raw => "raw",
            Framing::Zlib => "zlib",
            Framing::Gzip => "gzip",
        }
    }

    pub fn parse(s: &str) -> Option<Framing> {
        match s {
            "raw" => Some(Framing::Raw),
            "zlib" => Some(Framing::Zlib),
            "gzip" => Some(Framing::Gzip),
            _ => None,
        }
    }
}

pub use subject::{Caps, DecodeError, OutputLimit, StreamOutcome, Subject};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn framing_round_trips_through_str() {
        for f in [Framing::Raw, Framing::Zlib, Framing::Gzip] {
            assert_eq!(Framing::parse(f.as_str()), Some(f));
        }
        assert_eq!(Framing::parse("bogus"), None);
    }
}
