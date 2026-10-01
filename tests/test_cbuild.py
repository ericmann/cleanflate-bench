import json
from pathlib import Path

from cfbench import cbuild

FIX = Path(__file__).parent / "fixtures" / "cbuild"


def test_nohw_flags_on_aarch64_undefine_arm_crc():
    plan = cbuild.nohw_plan("aarch64")
    assert "-U__ARM_FEATURE_CRC32" in plan["cflags"]
    assert plan["control_identical_to_default"] is False
    assert "-U__ARM_FEATURE_CRC32" in cbuild.nohw_plan("arm64")["cflags"]


def test_nohw_on_x86_64_marks_control_identical():
    plan = cbuild.nohw_plan("x86_64")
    assert "-U__ARM_FEATURE_CRC32" not in plan["cflags"]
    assert plan["control_identical_to_default"] is True
    assert "no x86_64 hardware-CRC path" in plan["note"]


def test_cmake_cache_with_options_are_recorded():
    got = cbuild.parse_cmake_cache((FIX / "CMakeCache.txt").read_text())
    assert got == {
        "CMAKE_C_FLAGS": "",
        "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG",
        "WITH_AVX2": "ON",
        "WITH_GTEST": "OFF",
        "WITH_PCLMULQDQ": "ON",
    }


def test_up_to_date_build_is_skipped(tmp_path):
    info = tmp_path / "build-info.json"
    expected = {"id": "zng", "source_sha256": "abc", "recipe": {"cmake": ["-DX=1"]}}
    assert not cbuild.is_up_to_date(info, expected)
    info.write_text(json.dumps({**expected, "compiler": "cc"}))
    assert cbuild.is_up_to_date(info, expected)
    changed = {**expected, "source_sha256": "def"}
    assert not cbuild.is_up_to_date(info, changed)
    assert not cbuild.is_up_to_date(info, {**expected, "recipe": {"cmake": ["-DX=2"]}})
