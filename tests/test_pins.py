from pathlib import Path

from cfbench import pins

FIX = Path(__file__).parent / "fixtures" / "pins"


def _read(name):
    return (FIX / name).read_text()


def test_aarch64_crc_instructions_detected_and_crc32c_separated():
    r = pins.hw_crc(
        "aarch64", _read("aarch64_objdump.txt"), ["crc32_z"], {"arm_feature_crc32": True}
    )
    assert r["compiled_in"] is True
    assert r["evidence"]["crc32_instructions"] == 3  # crc32w, crc32x, crc32b
    assert r["evidence"]["crc32c_instructions"] == 1  # crc32cw is Castagnoli, counted apart
    assert r["evidence"]["__ARM_FEATURE_CRC32"] is True
    assert "disassembly" in r["method"] and "compiler-probe" in r["method"]
    assert "Castagnoli" in r["note"]


def test_aarch64_without_crc_instructions_is_not_compiled_in():
    r = pins.hw_crc("aarch64", "   0:\tret\n", [], {"arm_feature_crc32": False})
    assert r["compiled_in"] is False
    assert r["evidence"]["__ARM_FEATURE_CRC32"] is False


def test_x86_pclmul_detected_and_sse42_crc32c_separated():
    r = pins.hw_crc("x86_64", _read("x86_objdump.txt"), [], {})
    assert r["compiled_in"] is True
    assert r["evidence"]["pclmul_instructions"] == 3  # pclmulhqlqdq, pclmullqhqdq, vpclmulqdq
    assert r["evidence"]["sse42_crc32c_instructions"] == 2  # crc32q, crc32b
    assert "Castagnoli" in r["note"]


def test_zng_symbols_imply_runtime_dispatch():
    syms = [s.split()[-1] for s in _read("x86_nm.txt").splitlines() if " T " in s]
    r = pins.hw_crc(
        "x86_64", _read("x86_objdump.txt"), syms, {"cmake_options": {"WITH_PCLMULQDQ": "ON"}}
    )
    assert r["runtime_dispatch"] is True
    assert r["evidence"]["dispatch_symbols"] == ["crc32_pclmulqdq", "crc32_vpclmulqdq"]
    assert r["evidence"]["cmake_options"] == {"WITH_PCLMULQDQ": "ON"}
    assert "cmake-options" in r["method"] and "symbols" in r["method"]


def test_no_disassembly_leaves_compiled_in_unknown():
    r = pins.hw_crc("aarch64", None, [], {"note": "dyld shared cache"})
    assert r["compiled_in"] is None
    assert "dyld shared cache" in r["note"]


def test_lock_merge_preserves_other_machine():
    existing = {"machines": {"M-A": {"recorded_at": "a", "builds": {"zlib": {}}}}, "stale": 1}
    static = {"rust_toolchain": "1.89.0"}
    merged = pins.merge_lock(existing, static, "M-B", {"recorded_at": "b", "builds": {}})
    assert merged["machines"]["M-A"] == {"recorded_at": "a", "builds": {"zlib": {}}}
    assert merged["machines"]["M-B"]["recorded_at"] == "b"
    assert merged["rust_toolchain"] == "1.89.0"
    assert merged["schema"] == pins.LOCK_SCHEMA
    again = pins.merge_lock(merged, static, "M-B", {"recorded_at": "c", "builds": {}})
    assert again["machines"]["M-A"]["recorded_at"] == "a"
    assert again["machines"]["M-B"]["recorded_at"] == "c"


def test_rust_profile_matches_cargo_toml():
    p = pins.rust_profile()
    assert p["opt-level"] == 3
    assert p["lto"] == "fat"
    assert p["codegen-units"] == 1
    assert p["panic"] == "default"


def test_member_crates_add_no_profiles():
    root = Path(__file__).resolve().parent.parent
    for manifest in (root / "crates").glob("*/Cargo.toml"):
        assert "[profile" not in manifest.read_text(), manifest
