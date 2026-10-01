import platform

from cfbench import machine


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("CFB_MACHINE", "M-Z")
    assert machine.detect_machine() == "M-Z"


def test_known_platform_maps_via_config(monkeypatch):
    monkeypatch.delenv("CFB_MACHINE", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    assert machine.detect_machine() == "M-A"
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert machine.detect_machine() == "M-B"


def test_unknown_platform_gets_other_label(monkeypatch):
    monkeypatch.delenv("CFB_MACHINE", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Plan9")
    monkeypatch.setattr(platform, "machine", lambda: "mips")
    assert machine.detect_machine() == "other-Plan9-mips"
