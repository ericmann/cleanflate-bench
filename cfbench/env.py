"""Environment capture (SPEC §3.1). May read the wall clock (with rawio.py)."""

import os
import platform
import subprocess
import sys

from cfbench import config, paths, rawio
from cfbench.machine import detect_machine


def run_cmd(argv: list[str]) -> str | None:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout if out.stdout.strip() else out.stderr


def read_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _first_line(text: str | None) -> str | None:
    if text is None:
        return None
    lines = text.strip().splitlines()
    return lines[0].strip() if lines else None


class _Probe:
    def __init__(self, cmd, rd):
        self.cmd = cmd
        self.rd = rd
        self.errors: list[dict] = []

    def run(self, probe: str, argv: list[str]) -> str | None:
        try:
            out = self.cmd(argv)
        except Exception as e:  # noqa: BLE001 - a probe must never raise
            out = None
            self.errors.append({"probe": probe, "error": f"{type(e).__name__}: {e}"})
            return None
        if out is None:
            self.errors.append({"probe": probe, "error": f"command failed: {' '.join(argv)}"})
        return out

    def file(self, probe: str, path: str) -> str | None:
        out = self.rd(path)
        if out is None:
            self.errors.append({"probe": probe, "error": f"cannot read {path}"})
        return out


def _kv(text: str | None, sep: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        if sep in line:
            k, v = line.split(sep, 1)
            out[k.strip()] = v.strip()
    return out


def _int(s: str | None) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def _mac_probes(p: _Probe) -> dict:
    cpu = p.run("cpu_model", ["sysctl", "-n", "machdep.cpu.brand_string"])
    phys = _int(p.run("cores.physical", ["sysctl", "-n", "hw.physicalcpu"]))
    logi = _int(p.run("cores.logical", ["sysctl", "-n", "hw.logicalcpu"]))
    name = _first_line(p.run("os.name", ["sw_vers", "-productName"]))
    ver = _first_line(p.run("os.version", ["sw_vers", "-productVersion"]))
    batt = p.run("power.batt", ["pmset", "-g", "batt"])
    pm = p.run("power.pmset", ["pmset", "-g"])
    on_ac = None
    if batt is not None:
        on_ac = "AC Power" in batt
    low = None
    if pm is not None:
        lp = _kv(pm.replace("\t", " ").replace("  ", " "), " ")
        low = lp.get("lowpowermode") == "1" if "lowpowermode" in lp else False
    return {
        "cpu_model": _first_line(cpu),
        "cores": {"physical": phys, "logical": logi},
        "os": {"name": name, "version": ver},
        "power": {
            "on_ac": on_ac,
            "low_power_mode": low,
            "raw": {"batt": batt, "pmset": pm},
        },
        "governor": None,
        "thermal": lambda: p.run("thermal", ["pmset", "-g", "therm"]),
    }


def _linux_probes(p: _Probe) -> dict:
    lscpu = _kv(p.run("cpu_model", ["lscpu"]), ":")
    phys = None
    cps, sock = _int(lscpu.get("Core(s) per socket")), _int(lscpu.get("Socket(s)"))
    if cps is not None and sock is not None:
        phys = cps * sock
    logi = _int(lscpu.get("CPU(s)"))
    osr = _kv(p.file("os", "/etc/os-release"), "=")
    unq = {k: v.strip('"') for k, v in osr.items()}
    power_raw = {}
    on_ac = None
    base = "/sys/class/power_supply"
    for name in _list_supplies(p):
        typ = _first_line(p.file(f"power.{name}.type", f"{base}/{name}/type"))
        online = _first_line(p.file(f"power.{name}.online", f"{base}/{name}/online"))
        power_raw[name] = {"type": typ, "online": online}
        if typ == "Mains" and online is not None:
            on_ac = online == "1" or bool(on_ac)
    return {
        "cpu_model": lscpu.get("Model name"),
        "cores": {"physical": phys, "logical": logi},
        "os": {"name": unq.get("NAME"), "version": unq.get("VERSION")},
        "power": {"on_ac": on_ac, "low_power_mode": None, "raw": power_raw},
        "governor": _first_line(
            p.file("governor", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        ),
        "thermal": lambda: p.run("thermal", ["sensors", "-j"]),
    }


def _list_supplies(p: _Probe) -> list[str]:
    out = p.run("power.list", ["ls", "/sys/class/power_supply"])
    return sorted((out or "").split())


def _toolchains(p: _Probe) -> dict:
    cmds = {
        "rustc": ["rustc", "--version"],
        "cargo": ["cargo", "--version"],
        "cc": ["cc", "--version"],
        "cmake": ["cmake", "--version"],
        "python": [sys.executable, "--version"],
        "uv": ["uv", "--version"],
        "java": ["java", "-version"],
    }
    out = {}
    for k, argv in cmds.items():
        out[k] = _first_line(p.run(f"toolchains.{k}", argv))
    return out


def _repos() -> dict:
    g = rawio.bench_git()
    tag = sha = None
    try:
        rounds = config.load_json("rounds.json")
        primary = next(r for r in rounds["rounds"] if r["round"] == rounds["primary_round"])
        tag, sha = primary["tag"], primary["sha"]
    except (OSError, KeyError, StopIteration):
        pass
    return {
        "bench_sha": g["sha"],
        "bench_dirty": g["dirty"],
        "cleanflate_tag": tag,
        "cleanflate_sha": sha,
    }


def capture_environment(cmd=None, rd=None, system: str | None = None) -> dict:
    p = _Probe(cmd or run_cmd, rd or read_file)
    system = system or platform.system()
    info = _mac_probes(p) if system == "Darwin" else _linux_probes(p)
    thermal = info.pop("thermal")
    try:
        load = list(os.getloadavg())
    except OSError:
        load = None
        p.errors.append({"probe": "load_avg_start", "error": "getloadavg unavailable"})
    kernel = _first_line(p.run("kernel", ["uname", "-r"]))
    env = {
        "machine": detect_machine(),
        **info,
        "kernel": kernel,
        "load_avg_start": load,
        "thermal_start": thermal(),
        "toolchains": _toolchains(p),
        "repos": _repos(),
    }
    env["probe_errors"] = p.errors
    env["_system"] = system
    return env


def capture_end(env: dict, cmd=None) -> dict:
    out = dict(env)
    try:
        out["load_avg_end"] = list(os.getloadavg())
    except OSError:
        out["load_avg_end"] = None
    argv = ["pmset", "-g", "therm"] if env.get("_system") == "Darwin" else ["sensors", "-j"]
    out["thermal_end"] = (cmd or run_cmd)(argv)
    return out


def main() -> int:
    import json

    env = capture_environment()
    config.load_config()  # validates CFB_PROFILE
    prof = os.environ.get("CFB_PROFILE") or "full"
    path = rawio.write_raw(
        "env",
        {"kind": "env", "capture": env},
        machine=env["machine"],
        profile=prof,
        script="cfbench.env",
        environment=env,
    )
    with open(paths.ROOT / "environment.json", "w", encoding="utf-8") as f:
        json.dump(env, f, sort_keys=True, indent=1)
        f.write("\n")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
