"""Machine label detection (SPEC §3.1)."""

import os
import platform

from cfbench.config import load_config


def detect_machine() -> str:
    override = os.environ.get("CFB_MACHINE")
    if override:
        return override
    system, arch = platform.system(), platform.machine()
    return load_config("full")["machines"].get(f"{system}-{arch}", f"other-{system}-{arch}")
