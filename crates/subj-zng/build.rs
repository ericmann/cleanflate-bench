use std::path::PathBuf;
use std::process::Command;

fn main() {
    let root = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap()).join("../..");
    let base = root.join("build/c/zng");
    let lib = ["lib", "lib64"]
        .iter()
        .map(|d| base.join(d))
        .find(|d| d.join("libz-ng.a").exists())
        .unwrap_or_else(|| panic!("missing {}: run `make c-subjects`", base.display()));
    println!("cargo:rerun-if-changed={}", lib.join("libz-ng.a").display());
    println!("cargo:rustc-link-search=native={}", lib.display());
    // A plain link-arg lands after the rlibs, so the archive resolves their symbols.
    println!("cargo:rustc-link-arg-bins=-lz-ng");

    // Print sizeof/offsetof of zng_stream from the generated header, for the layout test.
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    let probe = out.join("probe.c");
    std::fs::write(
        &probe,
        r#"#include <stdio.h>
#include <stddef.h>
#include "zlib-ng.h"
int main(void) {
    printf("%zu", sizeof(zng_stream));
#define F(n) printf(",%zu", offsetof(zng_stream, n));
    F(next_in) F(avail_in) F(total_in) F(next_out) F(avail_out) F(total_out) F(msg)
    F(state) F(zalloc) F(zfree) F(opaque) F(data_type) F(adler) F(reserved)
    return 0;
}
"#,
    )
    .unwrap();
    let exe = out.join("probe");
    let cc = std::env::var("CC").unwrap_or_else(|_| "cc".to_string());
    let st = Command::new(&cc)
        .arg(&probe)
        .arg("-I")
        .arg(base.join("include"))
        .arg("-o")
        .arg(&exe)
        .status()
        .expect("run C compiler");
    assert!(st.success(), "probe compile failed");
    let o = Command::new(&exe).output().expect("run probe");
    println!(
        "cargo:rustc-env=ZNG_STREAM_LAYOUT={}",
        String::from_utf8(o.stdout).unwrap()
    );
}
