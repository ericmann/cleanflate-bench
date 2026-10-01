//! Minimal zlib stdin->stdout decompressor over miniz_oxide, for the binary-size comparison.

use miniz_oxide::inflate::stream::{inflate, InflateState};
use miniz_oxide::{DataFormat, MZError, MZFlush, MZStatus};
use std::io::{Read, Write};

const BUF: usize = 64 * 1024;

fn run() -> Result<(), String> {
    let mut state = InflateState::new_boxed(DataFormat::Zlib);
    let mut input = vec![0u8; BUF];
    let mut output = vec![0u8; BUF];
    let mut stdin = std::io::stdin().lock();
    let mut stdout = std::io::stdout().lock();
    let mut done = false;
    'outer: loop {
        let n = stdin.read(&mut input).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        let mut rest = &input[..n];
        loop {
            let r = inflate(&mut state, rest, &mut output, MZFlush::None);
            stdout
                .write_all(&output[..r.bytes_written])
                .map_err(|e| e.to_string())?;
            rest = &rest[r.bytes_consumed..];
            match r.status {
                Ok(MZStatus::StreamEnd) => {
                    done = true;
                    break 'outer;
                }
                Ok(_) if r.bytes_consumed != 0 || r.bytes_written != 0 => {}
                Ok(_) | Err(MZError::Buf) => break,
                Err(e) => return Err(format!("{e:?}")),
            }
        }
    }
    if !done {
        return Err("truncated input".to_string());
    }
    stdout.flush().map_err(|e| e.to_string())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}
