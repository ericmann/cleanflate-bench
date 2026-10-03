import json
from pathlib import Path

from cfbench import paths, size

FIX = Path(__file__).parent / "fixtures" / "size"

MAKEFILE_IN = """\
OBJC = $(OBJZ) $(OBJG)
OBJZ = adler32.o crc32.o deflate.o infback.o inffast.o inflate.o inftrees.o trees.o zutil.o
OBJG = compress.o uncompr.o gzclose.o gzlib.o gzread.o gzwrite.o
"""


def test_rust_build_command_sets_opt_level_and_strip():
    cmd = size.rust_build_cmd("cf", "3", stripped=True)
    assert cmd[:5] == ["cargo", "build", "--release", "-p", "min-cf"]
    assert "profile.release.opt-level=3" in cmd
    assert "profile.release.strip=true" in cmd
    assert cmd[cmd.index("--target-dir") + 1] == str(paths.ROOT / "target" / "size-3")
    small = size.rust_build_cmd("mox", "s", stripped=False)
    assert 'profile.release.opt-level="s"' in small
    assert 'profile.release.strip="none"' in small
    assert small[small.index("--target-dir") + 1].endswith("size-s-unstripped")


def test_bloat_command_uses_unstripped_dir_and_env_profile():
    cmd, envv = size.bloat_cmd("zrs", "s", 30)
    assert cmd[:3] == ["cargo", "bloat", "--release"]
    assert cmd[cmd.index("-n") + 1] == "30" and "--crates" in cmd
    assert cmd[cmd.index("--message-format") + 1] == "json"
    assert cmd[cmd.index("--target-dir") + 1].endswith("size-s-unstripped")
    assert envv == {"CARGO_PROFILE_RELEASE_OPT_LEVEL": "s", "CARGO_PROFILE_RELEASE_STRIP": "none"}


def test_c_link_flags_per_platform():
    linux = size.c_link_flags("Linux", "s")
    mac = size.c_link_flags("Darwin", "3")
    assert "-Os" in linux and "-Wl,--gc-sections" in linux and "-Wl,-dead_strip" not in linux
    assert "-O3" in mac and "-Wl,-dead_strip" in mac and "-Wl,--gc-sections" not in mac
    for flags in (linux, mac):
        assert {"-flto", "-ffunction-sections", "-fdata-sections"} <= set(flags)


def test_strip_uses_apple_strip_on_darwin():
    exe = Path("/x/min_zlib-3")
    assert size.strip_cmd("Darwin", exe) == ["xcrun", "strip", "/x/min_zlib-3"]
    assert size.strip_cmd("Linux", exe) == ["strip", "/x/min_zlib-3"]


def test_zlib_sources_come_from_objz():
    assert size.zlib_sources(MAKEFILE_IN) == [
        "adler32.c", "crc32.c", "deflate.c", "infback.c", "inffast.c",
        "inflate.c", "inftrees.c", "trees.c", "zutil.c",
    ]  # fmt: skip


def test_bloat_json_is_parsed_into_crate_rows():
    doc = json.loads((FIX / "bloat_crates.json").read_text())
    rows = size.parse_bloat(doc)
    assert [r["crate"] for r in rows] == ["std", "cleanflate", "min_cf", "[Unknown]", "__rustc"]
    assert rows[0]["bytes"] == 248424
    assert abs(rows[0]["share"] - 248424 / 291004) < 1e-12
    assert (
        0.98 < sum(r["share"] for r in rows) <= 1.0
    )  # the rest is code cargo-bloat leaves unattributed


def test_zsys_row_is_excluded_with_note():
    payload = {
        "programs": [
            {"subject": "zsys", "opt": "3", "bytes": None, "note": size.ZSYS_NOTE},
            {"subject": "cf", "opt": "3", "bytes": 1234},
        ],
        "bloat": [
            {
                "subject": "cf",
                "opt": "3",
                "doc": json.loads((FIX / "bloat_crates.json").read_text()),
            }
        ],
    }
    sizes, bloat = size.rows_from_payload(payload, "M-T")
    by = {r["subject"]: r for r in sizes}
    assert by["zsys"]["bytes"] is None and "dynamically linked" in by["zsys"]["note"]
    assert by["cf"]["bytes"] == 1234 and by["cf"]["note"] == ""
    assert len(bloat) == 5 and bloat[0]["machine"] == "M-T" and bloat[0]["opt"] == "3"


def test_derive_writes_pending_without_raw(tmp_path, monkeypatch):
    from cfbench import provenance

    monkeypatch.setattr(paths, "RAW", tmp_path / "none")
    monkeypatch.setattr(paths, "RESULTS", tmp_path / "results")
    size.derive_binary()
    rows, side = provenance.read_table("binary_size")
    assert rows == [] and side["pending"] == size.PENDING
