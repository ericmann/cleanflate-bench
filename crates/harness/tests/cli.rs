use harness::cli::run;
use harness::subject::{Caps, DecodeError, OutputLimit, StreamOutcome, Subject, ERR_OUTPUT_FULL};
use harness::Framing;
use harness::OneshotOutcome;
use serde_json::{json, Value};
use std::path::PathBuf;

/// A stored-block "decoder": output equals input.
struct IdentitySubject;

impl Subject for IdentitySubject {
    fn id() -> &'static str {
        "identity"
    }
    fn impl_version() -> String {
        "0".to_string()
    }
    fn caps() -> Caps {
        Caps {
            framings: vec![Framing::Raw, Framing::Zlib, Framing::Gzip],
            oneshot: true,
            stream: true,
            adler32: false,
            crc32: true,
            dictionary: false,
            output_limit: OutputLimit::Caller,
        }
    }
    fn oneshot(
        _f: Framing,
        input: &[u8],
        out: &mut [u8],
        _dict: Option<&[u8]>,
    ) -> Result<OneshotOutcome, DecodeError> {
        // A NUL byte terminates the "stream"; the NUL is consumed, anything after is trailing.
        let (produced, consumed) = match input.iter().position(|&b| b == 0) {
            Some(i) => (i, i + 1),
            None => (input.len(), input.len()),
        };
        if out.len() < produced {
            return Err(DecodeError::new(ERR_OUTPUT_FULL, "buffer too small"));
        }
        out[..produced].copy_from_slice(&input[..produced]);
        Ok(OneshotOutcome { produced, consumed })
    }
    fn stream(
        _f: Framing,
        input: &[u8],
        in_chunk: usize,
        out_buf: &mut [u8],
        sink: &mut dyn FnMut(&[u8]),
        _max_output: Option<u64>,
        _dict: Option<&[u8]>,
    ) -> Result<StreamOutcome, DecodeError> {
        let mut produced = 0u64;
        for piece in input.chunks(in_chunk) {
            for o in piece.chunks(out_buf.len()) {
                out_buf[..o.len()].copy_from_slice(o);
                sink(&out_buf[..o.len()]);
                produced += o.len() as u64;
            }
        }
        Ok(StreamOutcome {
            produced,
            consumed: input.len() as u64,
            limit_hit: false,
            trailing_bytes: 0,
        })
    }
    fn adler32(_data: &[u8]) -> Option<u32> {
        None
    }
    fn crc32(data: &[u8]) -> Option<u32> {
        Some(data.iter().fold(0u32, |a, b| a.wrapping_add(*b as u32)))
    }
    fn compress(_l: i32, _f: Framing, _i: &[u8]) -> Option<Result<Vec<u8>, DecodeError>> {
        None
    }
}

fn fixture(name: &str) -> String {
    let p: PathBuf = [env!("CARGO_MANIFEST_DIR"), "tests", "fixtures", name]
        .iter()
        .collect();
    p.to_string_lossy().into_owned()
}

fn call(args: &[&str]) -> (i32, Value) {
    let args: Vec<String> = args.iter().map(|s| s.to_string()).collect();
    let mut out = Vec::new();
    let code = run::<IdentitySubject>(&args, &mut out);
    let v = if out.is_empty() {
        Value::Null
    } else {
        serde_json::from_slice(&out).expect("one JSON object")
    };
    (code, v)
}

fn write_cell(tag: &str, expected: &str, mode: &str) -> String {
    let cell = json!({
        "framing": "raw", "mode": mode, "in_chunk": 7, "out_chunk": 5,
        "input": fixture("hello.txt"), "expected": expected,
        "warmup_ms": 1, "min_samples": 4, "min_sample_ms": 1,
    });
    let path = std::env::temp_dir().join(format!("cfb-cli-test-{tag}-{}.json", std::process::id()));
    std::fs::write(&path, cell.to_string()).unwrap();
    path.to_string_lossy().into_owned()
}

#[test]
fn info_lists_capabilities() {
    let (code, v) = call(&["info"]);
    assert_eq!(code, 0);
    assert_eq!(v["id"], "identity");
    assert_eq!(v["checksums"], json!(["crc32"]));
    assert_eq!(v["output_limit"], "caller");
}

#[test]
fn bench_reports_output_mismatch() {
    let cell = write_cell("mismatch", &fixture("hello.raw"), "oneshot");
    let (code, v) = call(&["bench", "--cell", &cell]);
    assert_eq!(code, 0);
    assert_eq!(v["ok"], false);
    assert_eq!(v["error"], "output mismatch");
}

#[test]
fn bench_times_a_matching_cell_in_both_modes() {
    for mode in ["oneshot", "stream"] {
        let cell = write_cell(mode, &fixture("hello.txt"), mode);
        let (code, v) = call(&["bench", "--cell", &cell]);
        assert_eq!(code, 0);
        assert_eq!(v["ok"], true, "{v}");
        assert_eq!(v["samples_ns"].as_array().unwrap().len(), 4);
        // counters are process-global and tests run in parallel, so only the type is checked
        assert!(v["peak_heap_bytes"].is_u64());
    }
}

#[test]
fn decode_caller_limit_sets_limit_hit() {
    let limit = 5;
    let (code, v) = call(&[
        "decode",
        "--framing",
        "raw",
        "--mode",
        "stream",
        "--input",
        &fixture("hello.txt"),
        "--in-chunk",
        "4",
        "--out-chunk",
        "3",
        "--max-output",
        &limit.to_string(),
    ]);
    assert_eq!(code, 0);
    assert_eq!(v["ok"], false);
    assert_eq!(v["limit_hit"], true);
    assert_eq!(v["produced"], limit);
}

#[test]
fn decode_without_limit_hashes_output() {
    let (_, v) = call(&[
        "decode",
        "--framing",
        "raw",
        "--mode",
        "oneshot",
        "--input",
        &fixture("hello.txt"),
    ]);
    assert_eq!(v["ok"], true);
    let len = std::fs::metadata(fixture("hello.txt")).unwrap().len();
    assert_eq!(v["produced"], len);
    assert_eq!(v["sha256"].as_str().unwrap().len(), 64);
}

#[test]
fn unsupported_checksum_reports_ok_false() {
    let (code, v) = call(&[
        "checksum",
        "--algo",
        "adler32",
        "--size",
        "64",
        "--seed",
        "1",
        "--warmup-ms",
        "1",
        "--min-samples",
        "3",
        "--min-sample-ms",
        "1",
    ]);
    assert_eq!(code, 0);
    assert_eq!(v["ok"], false);
    assert_eq!(v["error"], "unsupported");
}

#[test]
fn supported_checksum_is_deterministic_for_a_seed() {
    let run_once = || {
        call(&[
            "checksum",
            "--algo",
            "crc32",
            "--size",
            "64",
            "--seed",
            "9",
            "--warmup-ms",
            "1",
            "--min-samples",
            "3",
            "--min-sample-ms",
            "1",
        ])
        .1
    };
    let a = run_once();
    assert_eq!(a["ok"], true);
    assert_eq!(a["value"], run_once()["value"]);
}

#[test]
fn usage_errors_exit_two() {
    assert_eq!(call(&[]).0, 2);
    assert_eq!(call(&["frobnicate"]).0, 2);
    assert_eq!(call(&["bench"]).0, 2);
}

#[test]
fn oneshot_decode_reports_consumed_and_trailing() {
    let path = std::env::temp_dir().join(format!("cfb-cli-trail-{}.bin", std::process::id()));
    std::fs::write(&path, b"abc\0xy").unwrap();
    let (_, v) = call(&[
        "decode",
        "--framing",
        "raw",
        "--mode",
        "oneshot",
        "--input",
        path.to_str().unwrap(),
    ]);
    assert_eq!(v["ok"], true);
    assert_eq!(v["produced"], 3);
    assert_eq!(v["consumed"], 4);
    assert_eq!(v["trailing_bytes"], 2);
}
