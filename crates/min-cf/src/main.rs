//! Minimal zlib stdin->stdout decompressor over cleanflate, for the binary-size comparison.

use cleanflate::{Decompressor, Format, Options, Status};
use std::io::{Read, Write};

const BUF: usize = 64 * 1024;

fn run() -> Result<(), String> {
    let mut d = Decompressor::new(Format::Zlib, Options::default());
    let mut input = vec![0u8; BUF];
    let mut output = vec![0u8; BUF];
    let mut stdin = std::io::stdin().lock();
    let mut stdout = std::io::stdout().lock();
    loop {
        let n = stdin.read(&mut input).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        let mut rest = &input[..n];
        loop {
            let p = d.decompress(rest, &mut output).map_err(|e| e.to_string())?;
            stdout
                .write_all(&output[..p.produced])
                .map_err(|e| e.to_string())?;
            rest = &rest[p.consumed..];
            let stalled = p.consumed == 0 && p.produced == 0;
            match p.status {
                Status::NeedsInput => break,
                Status::OutputFull if !stalled => {}
                Status::Done if !rest.is_empty() && !stalled => {}
                _ => break,
            }
        }
    }
    d.finish().map_err(|e| e.to_string())?;
    stdout.flush().map_err(|e| e.to_string())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}
