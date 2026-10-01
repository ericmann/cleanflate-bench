//! `cfb-zlib`: the zlib API over the pinned build in `build/c/zlib`.

use zlibapi::{Api, Variant};

struct Zlib;

impl Variant for Zlib {
    const ID: &'static str = "zlib";
    const COMPRESS: bool = true;
}

fn main() {
    harness::cli::run_main::<Api<Zlib>>()
}
