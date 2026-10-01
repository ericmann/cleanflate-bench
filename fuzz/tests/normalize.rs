use cffuzz::{
    check, compare, decode_cf, decode_mox, decode_zlib, decode_zrs, Framing, Outcome, Reference,
};

/// Raw DEFLATE: one stored final block holding "abc".
const STORED_ABC: [u8; 8] = [0x01, 0x03, 0x00, 0xfc, 0xff, b'a', b'b', b'c'];

fn gzip_member() -> Vec<u8> {
    // header, stored block "abc", CRC-32 of "abc" (0x352441c2), ISIZE 3
    let mut v = vec![0x1f, 0x8b, 8, 0, 0, 0, 0, 0, 0, 255];
    v.extend_from_slice(&STORED_ABC);
    v.extend_from_slice(&[0xc2, 0x41, 0x24, 0x35, 3, 0, 0, 0]);
    v
}

#[test]
fn trailing_data_is_normalized() {
    let mut raw = STORED_ABC.to_vec();
    raw.extend_from_slice(b"junk");
    for out in [
        decode_cf(Framing::Raw, &raw),
        decode_zlib(Framing::Raw, &raw),
        decode_zrs(Framing::Raw, &raw),
        decode_mox(Framing::Raw, &raw),
    ] {
        assert_eq!(out, Outcome::Ok(b"abc".to_vec()));
    }
    // gzip: trailing garbage after the last member, and a second concatenated member
    let mut gz = gzip_member();
    gz.extend_from_slice(b"junk");
    assert!(compare(
        &decode_cf(Framing::Gzip, &gz),
        &decode_zlib(Framing::Gzip, &gz)
    )
    .is_ok());
    assert!(compare(
        &decode_cf(Framing::Gzip, &gz),
        &decode_zrs(Framing::Gzip, &gz)
    )
    .is_ok());
    let mut two = gzip_member();
    two.extend_from_slice(&gzip_member());
    for out in [
        decode_cf(Framing::Gzip, &two),
        decode_zlib(Framing::Gzip, &two),
        decode_zrs(Framing::Gzip, &two),
    ] {
        assert_eq!(out, Outcome::Ok(b"abcabc".to_vec()));
    }
    // the first byte picks the framing: 0 is raw
    let mut input = vec![0u8];
    input.extend_from_slice(&raw);
    assert_eq!(check(Reference::Zlib, &input), Ok(()));
    assert_eq!(check(Reference::Mox, &input), Ok(()));
}

#[test]
fn both_capped_is_agreement() {
    assert!(compare(&Outcome::Capped, &Outcome::Capped).is_ok());
    assert!(compare(&Outcome::Rejected, &Outcome::Rejected).is_ok());
    assert!(compare(&Outcome::Capped, &Outcome::Ok(vec![])).is_err());
    // the cap is the SPEC value
    assert_eq!(cffuzz::CAP, 64 << 20);
}

#[test]
fn accept_vs_reject_is_divergence() {
    let ok = Outcome::Ok(b"abc".to_vec());
    let message = compare(&ok, &Outcome::Rejected).unwrap_err();
    assert!(
        message.contains("accepted 3 bytes") && message.contains("rejected"),
        "{message}"
    );
    assert!(compare(&ok, &Outcome::Ok(b"abd".to_vec())).is_err());
    // a truncated stream is rejected by all four decoders
    let cut = &STORED_ABC[..6];
    for out in [
        decode_cf(Framing::Raw, cut),
        decode_zlib(Framing::Raw, cut),
        decode_zrs(Framing::Raw, cut),
        decode_mox(Framing::Raw, cut),
    ] {
        assert_eq!(out, Outcome::Rejected);
    }
}
