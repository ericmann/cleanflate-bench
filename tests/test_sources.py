import json
from pathlib import Path

import pytest

from cfbench import paths, sources

META = json.loads((Path(__file__).parent / "fixtures" / "pins" / "cargo_metadata.json").read_text())


def test_cargo_metadata_resolves_package_dirs(tmp_path):
    dirs = sources.package_dirs(META)
    assert dirs["zlib-rs"] == Path("/reg/zlib-rs-0.6.8")
    assert dirs["miniz_oxide"] == Path("/reg/miniz_oxide-0.9.1")
    meta = {
        "packages": [
            {"name": n, "manifest_path": str(tmp_path / n / "Cargo.toml")}
            for n in ("zlib-rs", "libz-rs-sys", "miniz_oxide")
        ]
    }
    for n in ("zlib-rs", "libz-rs-sys", "miniz_oxide"):
        (tmp_path / n).mkdir()
    assert sources.source_root("zrs", meta) == tmp_path / "zlib-rs"
    assert sources.extra_roots("zrs", meta) == [tmp_path / "libz-rs-sys"]
    assert sources.source_root("mox", meta) == tmp_path / "miniz_oxide"
    assert sources.extra_roots("mox", meta) == []


def test_missing_root_names_the_make_target(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path)
    with pytest.raises(sources.SourceMissing, match="make fetch"):
        sources.source_root("cf")
    with pytest.raises(sources.SourceMissing, match="make c-subjects"):
        sources.source_root("zlib")
    with pytest.raises(sources.SourceMissing, match="cargo fetch"):
        sources.source_root("mox", {"packages": []})
