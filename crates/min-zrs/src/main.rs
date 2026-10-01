//! Minimal zlib stdin->stdout decompressor over zlib-rs (zlib API), for the binary-size comparison.

use libz_rs_sys as z;
use std::ffi::c_int;
use std::io::{Read, Write};

const BUF: usize = 64 * 1024;

fn run() -> Result<(), String> {
    let mut strm = Box::new(z::z_stream::default());
    let rc = unsafe {
        z::inflateInit2_(
            &mut *strm,
            15,
            z::zlibVersion(),
            std::mem::size_of::<z::z_stream>() as c_int,
        )
    };
    if rc != z::Z_OK {
        return Err(format!("inflateInit2 failed ({rc})"));
    }
    let result = pump(&mut strm);
    unsafe { z::inflateEnd(&mut *strm) };
    result
}

fn pump(strm: &mut z::z_stream) -> Result<(), String> {
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
        strm.next_in = input.as_mut_ptr();
        strm.avail_in = n as u32;
        loop {
            strm.next_out = output.as_mut_ptr();
            strm.avail_out = BUF as u32;
            let rc = unsafe { z::inflate(strm, z::Z_NO_FLUSH) };
            let produced = BUF - strm.avail_out as usize;
            stdout
                .write_all(&output[..produced])
                .map_err(|e| e.to_string())?;
            match rc {
                z::Z_STREAM_END => {
                    done = true;
                    break 'outer;
                }
                z::Z_OK if strm.avail_in != 0 || strm.avail_out == 0 => {}
                z::Z_OK | z::Z_BUF_ERROR => break,
                other => return Err(format!("inflate failed ({other})")),
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
