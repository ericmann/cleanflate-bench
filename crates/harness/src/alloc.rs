//! Counting global allocator, plus C allocation callbacks so C subjects' heap is counted.

use std::alloc::{GlobalAlloc, Layout, System};
use std::ffi::c_void;
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};

pub struct Counting;

static CURRENT: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);
static CALLS: AtomicUsize = AtomicUsize::new(0);

fn add(n: usize) {
    let cur = CURRENT.fetch_add(n, Relaxed) + n;
    PEAK.fetch_max(cur, Relaxed);
    CALLS.fetch_add(1, Relaxed);
}

fn sub(n: usize) {
    CURRENT.fetch_sub(n, Relaxed);
}

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let p = unsafe { System.alloc(layout) };
        if !p.is_null() {
            add(layout.size());
        }
        p
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let p = unsafe { System.alloc_zeroed(layout) };
        if !p.is_null() {
            add(layout.size());
        }
        p
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) };
        sub(layout.size());
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let p = unsafe { System.realloc(ptr, layout, new_size) };
        if !p.is_null() {
            sub(layout.size());
            add(new_size);
        }
        p
    }
}

#[global_allocator]
static GLOBAL: Counting = Counting;

/// Set the peak to the current live byte count.
pub fn reset_peak() {
    PEAK.store(CURRENT.load(Relaxed), Relaxed);
    CALLS.store(0, Relaxed);
}

pub fn peak_bytes() -> usize {
    PEAK.load(Relaxed)
}

pub fn current_bytes() -> usize {
    CURRENT.load(Relaxed)
}

pub fn alloc_calls() -> usize {
    CALLS.load(Relaxed)
}

const HEADER: usize = 16;

/// zlib-style `alloc_func`: allocates `items * size` bytes through the counting allocator.
///
/// # Safety
/// Callable from C with any `opaque`; the returned pointer must be released with [`c_zfree`].
pub unsafe extern "C" fn c_zalloc(_opaque: *mut c_void, items: u32, size: u32) -> *mut c_void {
    let Some(total) = (items as usize)
        .checked_mul(size as usize)
        .and_then(|n| n.checked_add(HEADER))
    else {
        return std::ptr::null_mut();
    };
    let Ok(layout) = Layout::from_size_align(total, HEADER) else {
        return std::ptr::null_mut();
    };
    let p = unsafe { std::alloc::alloc(layout) };
    if p.is_null() {
        return std::ptr::null_mut();
    }
    unsafe {
        (p as *mut usize).write(total);
        p.add(HEADER) as *mut c_void
    }
}

/// zlib-style `free_func` matching [`c_zalloc`].
///
/// # Safety
/// `ptr` must be null or a pointer returned by [`c_zalloc`] not yet freed.
pub unsafe extern "C" fn c_zfree(_opaque: *mut c_void, ptr: *mut c_void) {
    if ptr.is_null() {
        return;
    }
    unsafe {
        let base = (ptr as *mut u8).sub(HEADER);
        let total = (base as *mut usize).read();
        std::alloc::dealloc(base, Layout::from_size_align_unchecked(total, HEADER));
    }
}
