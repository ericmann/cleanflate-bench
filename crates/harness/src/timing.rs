//! Warm-up, calibration and sampling loop. Single-threaded.

use crate::subject::DecodeError;
use std::time::{Duration, Instant};

#[derive(Clone, Debug)]
pub struct Measurement {
    pub iters_per_sample: u64,
    pub samples_ns: Vec<f64>,
}

type Op<'a> = &'a mut dyn FnMut() -> Result<(), DecodeError>;

fn run_iters(op: Op, iters: u64) -> Result<Duration, DecodeError> {
    let start = Instant::now();
    for _ in 0..iters {
        op()?;
    }
    Ok(start.elapsed())
}

/// Warm up for `warmup_ms`, calibrate `iters` so one sample lasts at least
/// `min_sample_ms`, then collect `min_samples` samples of `elapsed_ns / iters`.
pub fn measure(
    op: Op,
    warmup_ms: u64,
    min_samples: u32,
    min_sample_ms: u64,
) -> Result<Measurement, DecodeError> {
    let warm_end = Instant::now() + Duration::from_millis(warmup_ms);
    loop {
        op()?;
        if Instant::now() >= warm_end {
            break;
        }
    }
    let target = Duration::from_millis(min_sample_ms);
    let mut iters: u64 = 1;
    loop {
        let t = run_iters(op, iters)?;
        if t >= target {
            break;
        }
        iters = iters.saturating_mul(2);
    }
    let mut samples_ns = Vec::with_capacity(min_samples as usize);
    for _ in 0..min_samples {
        let t = run_iters(op, iters)?;
        samples_ns.push(t.as_nanos() as f64 / iters as f64);
    }
    Ok(Measurement {
        iters_per_sample: iters,
        samples_ns,
    })
}
