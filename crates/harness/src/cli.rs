//! Command-line front end shared by every `cfb-<id>` binary.
//!
//! Every subcommand prints exactly one JSON object on stdout. Exit status is 0 on success
//! and on a reported decode error (`"ok": false`), and 2 on usage errors.

use crate::alloc;
use crate::subject::{DecodeError, OutputLimit, Subject, ERR_OUTPUT_FULL, ERR_UNSUPPORTED};
use crate::timing;
use crate::Framing;
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::hint::black_box;
use std::io::Write;
use std::panic::{catch_unwind, resume_unwind, AssertUnwindSafe};

struct LimitHit;

#[derive(Deserialize)]
struct Cell {
    framing: String,
    mode: String,
    in_chunk: usize,
    out_chunk: usize,
    input: String,
    expected: String,
    warmup_ms: u64,
    min_samples: u32,
    min_sample_ms: u64,
}

struct Args {
    flags: Vec<(String, String)>,
}

impl Args {
    fn parse(args: &[String]) -> Result<Args, String> {
        let mut flags = Vec::new();
        let mut it = args.iter();
        while let Some(a) = it.next() {
            let Some(name) = a.strip_prefix("--") else {
                return Err(format!("unexpected argument {a:?}"));
            };
            let Some(v) = it.next() else {
                return Err(format!("flag --{name} needs a value"));
            };
            flags.push((name.to_string(), v.clone()));
        }
        Ok(Args { flags })
    }

    fn get(&self, name: &str) -> Option<&str> {
        self.flags
            .iter()
            .find(|(k, _)| k == name)
            .map(|(_, v)| v.as_str())
    }

    fn req(&self, name: &str) -> Result<&str, String> {
        self.get(name).ok_or_else(|| format!("missing --{name}"))
    }

    fn num<T: std::str::FromStr>(&self, name: &str) -> Result<T, String> {
        self.req(name)?
            .parse()
            .map_err(|_| format!("--{name} must be a number"))
    }

    fn opt_num<T: std::str::FromStr>(&self, name: &str) -> Result<Option<T>, String> {
        match self.get(name) {
            None => Ok(None),
            Some(v) => v
                .parse()
                .map(Some)
                .map_err(|_| format!("--{name} must be a number")),
        }
    }

    fn framing(&self) -> Result<Framing, String> {
        let s = self.req("framing")?;
        Framing::parse(s).ok_or_else(|| format!("unknown framing {s:?}"))
    }
}

fn print(out: &mut dyn Write, v: Value) {
    let _ = writeln!(out, "{v}");
}

fn read(path: &str) -> Result<Vec<u8>, String> {
    std::fs::read(path).map_err(|e| format!("cannot read {path}: {e}"))
}

/// Entry point for subject binaries.
pub fn run_main<S: Subject>() -> ! {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let stdout = std::io::stdout();
    let mut lock = stdout.lock();
    let code = run::<S>(&args, &mut lock);
    let _ = lock.flush();
    std::process::exit(code)
}

/// Testable core of [`run_main`].
pub fn run<S: Subject>(args: &[String], out: &mut dyn Write) -> i32 {
    let Some((cmd, rest)) = args.split_first() else {
        eprintln!("usage: <info|bench|decode|checksum|compress> [flags]");
        return 2;
    };
    let parsed = match Args::parse(rest) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("error: {e}");
            return 2;
        }
    };
    let res = match cmd.as_str() {
        "info" => Ok(info::<S>()),
        "bench" => bench::<S>(&parsed),
        "decode" => decode::<S>(&parsed),
        "checksum" => checksum::<S>(&parsed),
        "compress" => compress::<S>(&parsed),
        other => Err(format!("unknown subcommand {other:?}")),
    };
    match res {
        Ok(v) => {
            print(out, v);
            0
        }
        Err(e) => {
            eprintln!("error: {e}");
            2
        }
    }
}

fn info<S: Subject>() -> Value {
    let caps = S::caps();
    let mut modes = Vec::new();
    if caps.oneshot {
        modes.push("oneshot");
    }
    if caps.stream {
        modes.push("stream");
    }
    let mut checksums = Vec::new();
    if caps.adler32 {
        checksums.push("adler32");
    }
    if caps.crc32 {
        checksums.push("crc32");
    }
    json!({
        "id": S::id(),
        "impl_version": S::impl_version(),
        "framings": caps.framings.iter().map(|f| f.as_str()).collect::<Vec<_>>(),
        "modes": modes,
        "checksums": checksums,
        "dictionary": caps.dictionary,
        "output_limit": caps.output_limit.as_str(),
    })
}

fn bench_fail(error: &str) -> Value {
    json!({
        "ok": false,
        "error": error,
        "input_bytes": null,
        "output_bytes": null,
        "iters_per_sample": null,
        "samples_ns": [],
        "peak_heap_bytes": null,
        "alloc_calls": null,
    })
}

fn bench<S: Subject>(a: &Args) -> Result<Value, String> {
    let path = a.req("cell")?;
    let cell: Cell = serde_json::from_slice(&read(path)?).map_err(|e| format!("bad cell: {e}"))?;
    let framing = Framing::parse(&cell.framing).ok_or("unknown framing in cell")?;
    let stream_mode = match cell.mode.as_str() {
        "oneshot" => false,
        "stream" => true,
        m => return Err(format!("unknown mode {m:?}")),
    };
    let input = read(&cell.input)?;
    let expected = read(&cell.expected)?;

    // Untimed correctness pass: byte-for-byte against `expected`.
    let got: Result<Vec<u8>, DecodeError> = if stream_mode {
        let mut buf = vec![0u8; cell.out_chunk];
        let mut acc = Vec::with_capacity(expected.len());
        S::stream(
            framing,
            &input,
            cell.in_chunk,
            &mut buf,
            &mut |b| acc.extend_from_slice(b),
            None,
            None,
        )
        .map(|_| acc)
    } else {
        let mut buf = vec![0u8; expected.len()];
        S::oneshot(framing, &input, &mut buf, None).map(|n| {
            buf.truncate(n);
            buf
        })
    };
    match got {
        Err(e) => return Ok(bench_fail(&e.to_string())),
        Ok(bytes) if bytes != expected => return Ok(bench_fail("output mismatch")),
        Ok(_) => {}
    }

    // Untimed heap pass. The one-shot output buffer is part of the measured footprint.
    let heap_pass = |out_len: usize| {
        let mut buf = vec![0u8; out_len];
        if stream_mode {
            let _ = S::stream(
                framing,
                &input,
                cell.in_chunk,
                &mut buf,
                &mut |b| {
                    black_box(b);
                },
                None,
                None,
            );
        } else {
            let _ = black_box(S::oneshot(framing, &input, &mut buf, None));
        }
    };
    let out_len = if stream_mode {
        cell.out_chunk
    } else {
        expected.len()
    };
    let base = alloc::current_bytes();
    alloc::reset_peak();
    heap_pass(out_len);
    let peak = alloc::peak_bytes().saturating_sub(base);
    let calls = alloc::alloc_calls();

    // Timed loop with a pre-allocated output buffer.
    let mut buf = vec![0u8; out_len];
    let m = {
        let mut op = || -> Result<(), DecodeError> {
            if stream_mode {
                let r = S::stream(
                    framing,
                    &input,
                    cell.in_chunk,
                    &mut buf,
                    &mut |b| {
                        black_box(b);
                    },
                    None,
                    None,
                )?;
                black_box(r.produced);
            } else {
                black_box(S::oneshot(framing, &input, &mut buf, None)?);
            }
            Ok(())
        };
        timing::measure(
            &mut op,
            cell.warmup_ms,
            cell.min_samples,
            cell.min_sample_ms,
        )
    };
    match m {
        Err(e) => Ok(bench_fail(&e.to_string())),
        Ok(m) => Ok(json!({
            "ok": true,
            "error": null,
            "input_bytes": input.len(),
            "output_bytes": expected.len(),
            "iters_per_sample": m.iters_per_sample,
            "samples_ns": m.samples_ns,
            "peak_heap_bytes": peak,
            "alloc_calls": calls,
        })),
    }
}

struct DecodeResult {
    error: Option<DecodeError>,
    produced: u64,
    consumed: u64,
    trailing: u64,
    limit_hit: bool,
    sha256: String,
}

fn decode<S: Subject>(a: &Args) -> Result<Value, String> {
    let framing = a.framing()?;
    let mode = a.req("mode")?;
    let input = read(a.req("input")?)?;
    let max_output: Option<u64> = a.opt_num("max-output")?;
    let dict = match a.get("dictionary") {
        Some(p) => Some(read(p)?),
        None => None,
    };
    let mut sink_file = match a.get("output") {
        Some(p) => Some(std::io::BufWriter::new(
            std::fs::File::create(p).map_err(|e| format!("cannot create {p}: {e}"))?,
        )),
        None => None,
    };
    let mut hasher = Sha256::new();
    let mut produced: u64 = 0;
    let mut r = DecodeResult {
        error: None,
        produced: 0,
        consumed: 0,
        trailing: 0,
        limit_hit: false,
        sha256: String::new(),
    };
    match mode {
        "stream" => {
            let in_chunk: usize = a.num("in-chunk")?;
            let out_chunk: usize = a.num("out-chunk")?;
            let mut buf = vec![0u8; out_chunk];
            let caller_limit = max_output.filter(|_| S::caps().output_limit == OutputLimit::Caller);
            let res = catch_unwind(AssertUnwindSafe(|| {
                S::stream(
                    framing,
                    &input,
                    in_chunk,
                    &mut buf,
                    &mut |b| {
                        let take = match caller_limit {
                            Some(lim) => (lim.saturating_sub(produced) as usize).min(b.len()),
                            None => b.len(),
                        };
                        hasher.update(&b[..take]);
                        if let Some(f) = sink_file.as_mut() {
                            let _ = f.write_all(&b[..take]);
                        }
                        produced += take as u64;
                        if take < b.len() {
                            resume_unwind(Box::new(LimitHit));
                        }
                    },
                    max_output,
                    dict.as_deref(),
                )
            }));
            match res {
                Ok(Ok(o)) => {
                    r.consumed = o.consumed;
                    r.trailing = o.trailing_bytes;
                    r.limit_hit = o.limit_hit;
                }
                Ok(Err(e)) => r.error = Some(e),
                Err(p) if p.is::<LimitHit>() => r.limit_hit = true,
                Err(p) => resume_unwind(p),
            }
        }
        "oneshot" => {
            let mut size = match max_output {
                Some(m) => m as usize,
                None => (input.len().saturating_mul(4)).max(1 << 16),
            };
            loop {
                let mut buf = vec![0u8; size];
                match S::oneshot(framing, &input, &mut buf, dict.as_deref()) {
                    Ok(n) => {
                        hasher.update(&buf[..n]);
                        if let Some(f) = sink_file.as_mut() {
                            let _ = f.write_all(&buf[..n]);
                        }
                        produced = n as u64;
                        r.consumed = input.len() as u64;
                        break;
                    }
                    Err(e) if e.kind == ERR_OUTPUT_FULL && max_output.is_some() => {
                        r.limit_hit = true;
                        r.error = Some(e);
                        break;
                    }
                    Err(e) if e.kind == ERR_OUTPUT_FULL && size < (1usize << 34) => {
                        size = size.saturating_mul(2);
                    }
                    Err(e) => {
                        r.error = Some(e);
                        break;
                    }
                }
            }
        }
        m => return Err(format!("unknown mode {m:?}")),
    }
    if let Some(f) = sink_file.as_mut() {
        let _ = f.flush();
    }
    r.produced = produced;
    r.sha256 = hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    let ok = r.error.is_none() && !r.limit_hit;
    let (kind, msg) = match (&r.error, r.limit_hit) {
        (Some(e), _) => (Some(e.kind.clone()), Some(e.message.clone())),
        (None, true) => (
            Some("limit".to_string()),
            Some("output limit hit".to_string()),
        ),
        (None, false) => (None, None),
    };
    Ok(json!({
        "ok": ok,
        "error_kind": kind,
        "error": msg,
        "produced": r.produced,
        "consumed": r.consumed,
        "trailing_bytes": r.trailing,
        "limit_hit": r.limit_hit,
        "sha256": r.sha256,
    }))
}

/// Deterministic input for checksum runs.
fn xorshift_bytes(seed: u64, n: usize) -> Vec<u8> {
    let mut s = seed | 1;
    let mut out = Vec::with_capacity(n);
    while out.len() < n {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        out.extend_from_slice(&s.to_le_bytes());
    }
    out.truncate(n);
    out
}

fn checksum<S: Subject>(a: &Args) -> Result<Value, String> {
    let algo = a.req("algo")?.to_string();
    let size: usize = a.num("size")?;
    let seed: u64 = a.num("seed")?;
    let warmup_ms: u64 = a.num("warmup-ms")?;
    let min_samples: u32 = a.num("min-samples")?;
    let min_sample_ms: u64 = a.num("min-sample-ms")?;
    let f: fn(&[u8]) -> Option<u32> = match algo.as_str() {
        "adler32" => S::adler32,
        "crc32" => S::crc32,
        other => return Err(format!("unknown algo {other:?}")),
    };
    let data = xorshift_bytes(seed, size);
    let Some(value) = f(&data) else {
        return Ok(json!({"ok": false, "error": ERR_UNSUPPORTED, "algo": algo, "size": size}));
    };
    let mut op = || -> Result<(), DecodeError> {
        black_box(f(black_box(&data)));
        Ok(())
    };
    let m = timing::measure(&mut op, warmup_ms, min_samples, min_sample_ms)
        .map_err(|e| e.to_string())?;
    Ok(json!({
        "ok": true,
        "algo": algo,
        "size": size,
        "value": value,
        "iters_per_sample": m.iters_per_sample,
        "samples_ns": m.samples_ns,
    }))
}

fn compress<S: Subject>(a: &Args) -> Result<Value, String> {
    let level: i32 = a.num("level")?;
    let framing = a.framing()?;
    let input = read(a.req("input")?)?;
    let output = a.req("output")?;
    match S::compress(level, framing, &input) {
        None => Ok(json!({"ok": false, "error": ERR_UNSUPPORTED})),
        Some(Err(e)) => Ok(json!({"ok": false, "error": e.to_string()})),
        Some(Ok(bytes)) => {
            std::fs::write(output, &bytes).map_err(|e| format!("cannot write {output}: {e}"))?;
            Ok(json!({"ok": true, "error": null, "output_bytes": bytes.len()}))
        }
    }
}
