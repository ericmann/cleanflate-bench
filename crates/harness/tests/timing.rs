use harness::timing::measure;
use harness::DecodeError;
use std::time::{Duration, Instant};

fn spin(us: u64) {
    let end = Instant::now() + Duration::from_micros(us);
    while Instant::now() < end {
        std::hint::spin_loop();
    }
}

#[test]
fn calibrates_iterations_to_min_sample_time() {
    let min_sample_ms = 5;
    let mut op = || -> Result<(), DecodeError> {
        spin(100);
        Ok(())
    };
    let m = measure(&mut op, 5, 3, min_sample_ms).unwrap();
    assert!(m.iters_per_sample > 1, "iters {}", m.iters_per_sample);
    for s in &m.samples_ns {
        let sample_ms = s * m.iters_per_sample as f64 / 1e6;
        assert!(
            sample_ms >= min_sample_ms as f64 * 0.5,
            "sample {sample_ms} ms"
        );
        assert!(*s >= 100_000.0 * 0.9, "per-iteration {s} ns");
    }
}

#[test]
fn collects_exactly_min_samples() {
    let mut calls = 0u64;
    let mut op = || -> Result<(), DecodeError> {
        calls += 1;
        Ok(())
    };
    let m = measure(&mut op, 0, 17, 1).unwrap();
    assert_eq!(m.samples_ns.len(), 17);
    assert!(calls >= 17 * m.iters_per_sample);
}

#[test]
fn op_error_is_propagated() {
    let mut op = || -> Result<(), DecodeError> { Err(DecodeError::new("bad", "boom")) };
    let e = measure(&mut op, 0, 3, 1).unwrap_err();
    assert_eq!(e.kind, "bad");
}
