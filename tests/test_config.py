import pytest

from cfbench.config import load_config


def test_full_profile_loads_without_profiles_key():
    cfg = load_config("full")
    assert "profiles" not in cfg
    assert cfg["perf"]["levels"] == [1, 6, 9]


def test_quick_profile_deep_merges_perf_section():
    cfg = load_config("quick")
    assert "profiles" not in cfg
    assert cfg["perf"]["levels"] == [6]
    assert cfg["perf"]["tiny"]["prefix_bytes"] == [256]
    # untouched siblings survive the deep merge
    assert cfg["perf"]["tiny"]["sources"][0] == "canterbury/alice29.txt"
    assert cfg["perf"]["small_in_chunk"] == 1024


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        load_config("nope")


def test_missing_key_raises_keyerror():
    cfg = load_config("full")
    with pytest.raises(KeyError):
        cfg["perf"]["no_such_key"]
