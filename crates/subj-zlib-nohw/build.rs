use std::path::PathBuf;

fn main() {
    let root = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("../..");
    let lib = root.join("build/c/zlib-nohw/lib");
    if !lib.join("libcfbz_nohw.a").exists() {
        panic!(
            "missing {}: run `make c-subjects`",
            lib.join("libcfbz_nohw.a").display()
        );
    }
    println!(
        "cargo:rerun-if-changed={}",
        lib.join("libcfbz_nohw.a").display()
    );
    println!("cargo:rustc-link-search=native={}", lib.display());
    // A plain link-arg lands after the zlibapi rlib, so the archive resolves its symbols.
    println!("cargo:rustc-link-arg-bins=-lcfbz_nohw");
}
