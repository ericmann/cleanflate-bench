"""Pinned third-party tools, installed into a repo-local root (tool-gap protocol on failure)."""

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from cfbench import config, paths


@dataclass(frozen=True)
class ToolStatus:
    name: str
    version: str
    path: str
    ok: bool
    error: str | None


def tools_root() -> Path:
    return paths.THIRD_PARTY / "tools"


def binary_path(binary: str) -> Path:
    return tools_root() / "bin" / binary


def install_command(name: str, version: str) -> list[str]:
    """`+stable` keeps tool builds off the pinned 1.89 toolchain of the benchmark workspace."""
    return [
        "cargo",
        "+stable",
        "install",
        "--locked",
        "--root",
        str(tools_root()),
        name,
        "--version",
        version,
    ]


def run_cmd(argv: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as e:
        return 127, str(e)
    return out.returncode, (out.stdout + out.stderr)


def _installed(binary: Path, version: str, version_args: list[str], runner) -> bool:
    if not binary.exists():
        return False
    rc, out = runner([str(binary), *version_args])
    return rc == 0 and version in out


def ensure(name: str, runner=run_cmd) -> ToolStatus:
    """Make sure the pinned tool is installed. Never raises; failures come back as ok=False."""
    spec = config.load_toml("tools.toml")[name]
    version, binary = spec["version"], binary_path(spec["binary"])
    vargs = spec["version_args"]
    try:
        if _installed(binary, version, vargs, runner):
            return ToolStatus(name, version, str(binary), True, None)
        rc, out = runner(install_command(name, version))
        if rc != 0:
            tail = " | ".join(out.strip().splitlines()[-3:])
            return ToolStatus(name, version, str(binary), False, f"install failed ({rc}): {tail}")
        if not _installed(binary, version, vargs, runner):
            return ToolStatus(name, version, str(binary), False, "installed but --version mismatch")
        return ToolStatus(name, version, str(binary), True, None)
    except Exception as e:  # noqa: BLE001 - a tool gap must not stop the run
        return ToolStatus(name, version, str(binary), False, f"{type(e).__name__}: {e}")


def all_names() -> list[str]:
    """The cargo-installed tools (those with a `binary`); JPlag has its own installer."""
    return sorted(n for n, spec in config.load_toml("tools.toml").items() if "binary" in spec)


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "ensure":
        print("usage: cfbench.tools ensure [names...]", file=sys.stderr)
        return 2
    names = argv[1:] or all_names()
    statuses = [asdict(ensure(n)) for n in names]
    print(json.dumps(statuses, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
