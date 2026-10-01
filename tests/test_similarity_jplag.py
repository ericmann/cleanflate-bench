import json
from pathlib import Path

from cfbench import config
from cfbench.similarity import jplag

FIX = Path(__file__).parent / "fixtures" / "jplag"


def test_language_listing_parse_detects_rust():
    langs = jplag.parse_languages((FIX / "help_languages.txt").read_text())
    assert "rust" in langs and "c" in langs and "cpp" in langs
    assert "Languages:" not in langs and all(not x.startswith("-") for x in langs)
    assert jplag.parse_languages("Usage: jplag\nno languages here\n") == []
    # a listing without Rust must read as unsupported
    assert "rust" not in jplag.parse_languages("Languages:\n  c\n  java\n")


def test_result_fixture_parsed_to_avg_and_max():
    m = jplag.parse_comparison((FIX / "comparison.json").read_text())
    assert m["avg"] == 0.17365913631473798 and m["max"] == 0.28709349593495936
    assert m["longest_match"] == 54.0 and m["max_length"] == 9096.0
    assert m["matches"] == 2


def test_result_archive_parsed_with_version_and_min_tokens(tmp_path):
    import zipfile

    archive = tmp_path / "r.jplag"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("comparisons/a-b.json", (FIX / "comparison.json").read_text())
        z.writestr("runInformation.json", (FIX / "runInformation.json").read_text())
        z.writestr("options.json", (FIX / "options.json").read_text())
    out = jplag.parse_result_archive(archive)
    assert out["jplag_version"] == "6.3.0" and out["min_tokens"] == 8 and out["avg"] > 0


def test_cross_language_pairs_marked_not_applicable():
    cfg = config.load_config("full")
    plist = jplag.all_pairs(cfg)
    by = {(p["left"], p["right"]): p for p in plist}
    assert ("zlib", "zng") in by and by[("zlib", "zng")]["role"] == "context"
    assert not by[("zlib", "zng")]["cross_language"]
    for key in (("zrs", "zng"), ("cf", "zlib"), ("cf", "zng")):
        assert (
            jplag.classify(by[key])["status"]
            == jplag.NOT_APPLICABLE
            == ("not applicable (cross-language)")
        )
    for key in (("zrs", "mox"), ("cf", "zrs"), ("cf", "mox"), ("zlib", "zng")):
        assert jplag.classify(by[key])["status"] == "pending"


def test_java_major_parses_modern_and_legacy_versions():
    assert jplag.java_major('openjdk version "21.0.12.1" 2026-08-18') == 21
    assert jplag.java_major('java version "1.8.0_392"') == 8
    assert jplag.java_major('openjdk version "25" 2025-09-16') == 25
    assert jplag.java_major("garbage") is None


def test_pinned_tool_entries_cover_both_machines():
    s = config.load_toml("tools.toml")["jplag"]
    assert s["version"] == "6.3.0" and len(s["sha256"]) == 64 and s["min_java"] == 25
    assert set(s["jre"]) == {"Linux-x86_64", "Darwin-arm64"}
    assert all(
        len(v["sha256"]) == 64 and v["url"].startswith("https://") for v in s["jre"].values()
    )
    assert json.dumps(sorted(config.load_toml("tools.toml")))  # table names parse
