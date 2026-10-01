use std::path::PathBuf;

fn main() {
    let root = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("..");
    let lib = root.join("build/c/zlib/lib");
    let archive = lib.join("libcfbz_default.a");
    if !archive.exists() {
        panic!("missing {}: run `make c-subjects`", archive.display());
    }
    println!("cargo:rerun-if-changed={}", archive.display());
    println!("cargo:rustc-link-search=native={}", lib.display());
    println!("cargo:rustc-link-lib=static=cfbz_default");
}
