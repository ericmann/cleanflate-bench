fn main() {
    // The platform zlib, dynamically linked as installed (SPEC 2.2).
    println!("cargo:rustc-link-arg-bins=-lz");
}
