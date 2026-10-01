use harness::alloc;
use std::sync::Mutex;

// The counters are process-global, so serialise the tests in this file.
static LOCK: Mutex<()> = Mutex::new(());

const BIG: usize = 64 << 20;
const SLACK: usize = 8 << 20;

#[test]
fn peak_tracks_largest_live_allocation() {
    let _g = LOCK.lock().unwrap_or_else(|e| e.into_inner());
    alloc::reset_peak();
    let big = vec![1u8; BIG];
    let small = vec![2u8; 1024];
    drop(big);
    let peak = alloc::peak_bytes();
    assert!(peak >= BIG, "peak {peak}");
    assert!(peak < BIG + SLACK, "peak {peak}");
    assert!(alloc::alloc_calls() >= 2);
    drop(small);
}

#[test]
fn c_zalloc_round_trip_is_counted() {
    let _g = LOCK.lock().unwrap_or_else(|e| e.into_inner());
    alloc::reset_peak();
    let items = 1000u32;
    let size = 1000u32;
    let p = unsafe { alloc::c_zalloc(std::ptr::null_mut(), items, size) };
    assert!(!p.is_null());
    assert_eq!(p as usize % 16, 0);
    unsafe { std::ptr::write_bytes(p as *mut u8, 0xab, (items * size) as usize) };
    assert!(alloc::peak_bytes() >= (items * size) as usize);
    unsafe { alloc::c_zfree(std::ptr::null_mut(), p) };
    assert!(alloc::current_bytes() < SLACK);
    unsafe { alloc::c_zfree(std::ptr::null_mut(), std::ptr::null_mut()) };
}

#[test]
fn dealloc_and_realloc_are_counted() {
    let _g = LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let base = alloc::current_bytes() as i64;
    let mut v = Vec::<u8>::with_capacity(BIG / 2);
    v.reserve_exact(BIG);
    v.push(1);
    let grown = alloc::current_bytes() as i64 - base;
    assert!(
        grown >= BIG as i64 && grown < (BIG + SLACK) as i64,
        "grown {grown}"
    );
    drop(v);
    let after = alloc::current_bytes() as i64 - base;
    assert!(after < SLACK as i64, "after {after}");
}
