import pytest

from cfbench import config, decomp_paths


def tree(tmp_path, names):
    for n in names:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    return tmp_path


def test_globs_resolve_sorted_and_deduplicated(tmp_path):
    root = tree(
        tmp_path, ["src/b.rs", "src/a.rs", "src/sub/c.rs", "src/tests/t.rs", "src/skip.rs", "x.txt"]
    )
    spec = {"include": ["src/**/*.rs", "src/a.rs"], "exclude": ["src/tests/**", "src/skip.rs"]}
    got = decomp_paths.resolve("cf", [root], spec)
    assert [p.relative_to(root).as_posix() for p in got] == ["src/a.rs", "src/b.rs", "src/sub/c.rs"]
    assert got == sorted(set(got))


def test_extra_include_uses_extra_root(tmp_path):
    main = tree(tmp_path / "main", ["src/a.rs"])
    extra = tree(tmp_path / "extra", ["src/w.rs", "src/other.rs"])
    spec = {"include": ["src/*.rs"], "exclude": [], "extra_include": ["src/w.rs"]}
    got = decomp_paths.resolve("zrs", [main, extra], spec)
    assert got == sorted([main / "src" / "a.rs", extra / "src" / "w.rs"])


def test_unmatched_include_raises(tmp_path):
    root = tree(tmp_path, ["src/a.rs"])
    with pytest.raises(decomp_paths.StaleManifest, match="nope.rs"):
        decomp_paths.resolve("cf", [root], {"include": ["src/a.rs", "src/nope.rs"], "exclude": []})
    with pytest.raises(decomp_paths.StaleManifest):
        decomp_paths.resolve("cf", [root], {"include": ["src/*.rs"], "extra_include": ["x"]})


def test_manifest_covers_all_five_subjects():
    manifest = config.load_toml("decomp_paths.toml")
    assert set(manifest) == {"cf", "zlib", "zng", "zrs", "mox"} == set(decomp_paths.SUBJECTS)
    for name, s in manifest.items():
        assert s["include"], name
        assert s["rationale"].strip(), name
        assert "exclude" in s
        assert not any("deflate" in pat for pat in s["include"]), name
        assert not any(pat.startswith("gz") for pat in s["include"]), name


def test_manifest_excludes_tests_for_cf():
    assert "src/tests/**" in config.load_toml("decomp_paths.toml")["cf"]["exclude"]
