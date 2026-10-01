#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    if let Err(message) = cffuzz::check(cffuzz::Reference::Mox, data) {
        panic!("{message}");
    }
});
