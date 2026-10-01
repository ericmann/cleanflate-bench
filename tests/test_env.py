import json
from pathlib import Path

from cfbench import env

FIX = Path(__file__).parent / "fixtures" / "env"

KEYS = {
    "machine",
    "cpu_model",
    "cores",
    "os",
    "kernel",
    "power",
    "governor",
    "load_avg_start",
    "thermal_start",
    "toolchains",
    "repos",
    "probe_errors",
}


def _fake(name):
    fx = json.loads((FIX / f"{name}.json").read_text())

    def cmd(argv):
        key = " ".join(["python" if a.endswith(("python3", "python")) else a for a in argv])
        return fx["cmds"].get(key)

    return cmd, fx["files"].get


def test_linux_fixture_capture_fills_every_key(monkeypatch):
    monkeypatch.setenv("CFB_MACHINE", "M-B")
    cmd, rd = _fake("linux")
    e = env.capture_environment(cmd=cmd, rd=rd, system="Linux")
    assert KEYS <= set(e)
    assert e["cpu_model"] == "AMD Ryzen 5 3400G with Radeon Vega Graphics"
    assert e["cores"] == {"physical": 4, "logical": 8}
    assert e["os"]["name"] == "Pop!_OS"
    assert e["governor"]
    assert e["toolchains"]["rustc"].startswith("rustc 1.89")
    assert set(e["toolchains"]) == {"rustc", "cargo", "cc", "cmake", "python", "uv", "java"}
    assert set(e["repos"]) == {"bench_sha", "bench_dirty", "cleanflate_tag", "cleanflate_sha"}
    assert set(e["power"]) == {"on_ac", "low_power_mode", "raw"}


def test_macos_fixture_capture_reads_pmset_and_sysctl(monkeypatch):
    monkeypatch.setenv("CFB_MACHINE", "M-A")
    cmd, rd = _fake("macos")
    e = env.capture_environment(cmd=cmd, rd=rd, system="Darwin")
    assert e["cpu_model"] == "Apple M4"
    assert e["cores"] == {"physical": 10, "logical": 10}
    assert e["os"] == {"name": "macOS", "version": "15.1"}
    assert e["power"]["on_ac"] is True
    assert e["power"]["low_power_mode"] is False
    assert e["governor"] is None
    assert "No thermal warning" in e["thermal_start"]


def test_failing_probe_records_error_not_exception(monkeypatch):
    monkeypatch.setenv("CFB_MACHINE", "M-B")

    def boom(argv):
        raise RuntimeError("nope")

    e = env.capture_environment(cmd=boom, rd=lambda p: None, system="Linux")
    assert e["cpu_model"] is None
    assert e["toolchains"]["rustc"] is None
    assert e["probe_errors"]
    assert {"probe", "error"} == set(e["probe_errors"][0])
    end = env.capture_end(e, cmd=lambda a: None)
    assert "load_avg_end" in end and end["thermal_end"] is None
