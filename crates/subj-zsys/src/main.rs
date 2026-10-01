//! `cfb-zsys`: the platform's installed zlib, dynamically linked.

use zlibapi::{Api, Variant};

struct Zsys;

impl Variant for Zsys {
    const ID: &'static str = "zsys";
    const COMPRESS: bool = false;
}

fn main() {
    harness::cli::run_main::<Api<Zsys>>()
}
