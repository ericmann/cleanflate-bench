//! `cfb-zlib-nohw`: the zlib API over the pinned build in `build/c/zlib-nohw`.

use zlibapi::{Api, Variant};

struct ZlibNohw;

impl Variant for ZlibNohw {
    const ID: &'static str = "zlib-nohw";
    const COMPRESS: bool = false;
}

fn main() {
    harness::cli::run_main::<Api<ZlibNohw>>()
}
