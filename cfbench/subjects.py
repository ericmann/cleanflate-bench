"""Registry of benchmark subjects and where their binaries live."""

import json
import os
import re
from dataclasses import dataclass

from cfbench import paths

ROUND_SUBJECT = re.compile(r"^cf-r([123])$")
BUILDS = ("release", "debug", "native", "round1", "round2", "round3")


@dataclass(frozen=True)
class SubjectSpec:
    id: str
    binary: str
    label: str
    language: str
    kind: str  # primary, secondary or control


SUBJECTS: dict[str, SubjectSpec] = {
    s.id: s
    for s in [
        SubjectSpec("cf", "cfb-cf", "cleanflate", "rust", "primary"),
        SubjectSpec("zlib", "cfb-zlib", "zlib", "c", "primary"),
        SubjectSpec("zlib-nohw", "cfb-zlib-nohw", "zlib (no hw CRC)", "c", "control"),
        SubjectSpec("zng", "cfb-zng", "zlib-ng", "c", "primary"),
        SubjectSpec("zrs", "cfb-zrs", "zlib-rs", "rust", "primary"),
        SubjectSpec("mox", "cfb-mox", "miniz_oxide", "rust", "primary"),
        SubjectSpec("zsys", "cfb-zsys", "system zlib", "c", "secondary"),
        SubjectSpec("cf-r1", "cfb-cf", "cleanflate round 1", "rust", "round"),
        SubjectSpec("cf-r2", "cfb-cf", "cleanflate round 2", "rust", "round"),
        SubjectSpec("cf-r3", "cfb-cf", "cleanflate round 3", "rust", "round"),
    ]
}


def binary_path(subject: str, build: str = "release"):
    """Path of a subject binary for a build variant.

    `native` is the `-C target-cpu=native` variant. Cleanflate round builds (`cf-r1`..`cf-r3`, or
    `cf` with build `round1`..`round3`) live in `target/round<N>/release/` (`make subjects-rounds`).
    """
    spec = SUBJECTS[subject]
    m = ROUND_SUBJECT.match(subject)
    if m:
        return paths.ROOT / "target" / f"round{m.group(1)}" / "release" / spec.binary
    if build == "release":
        return paths.ROOT / "target" / "release" / spec.binary
    if build == "debug":
        return paths.ROOT / "target" / "debug" / spec.binary
    if build == "native":
        return paths.ROOT / "target" / "native" / "release" / spec.binary
    if build in ("round1", "round2", "round3"):
        if subject != "cf":
            raise ValueError("round builds exist only for cf")
        return paths.ROOT / "target" / build / "release" / spec.binary
    raise ValueError(f"unknown build {build!r}")


def command(subject: str, build: str = "release") -> list[str]:
    """argv prefix to run a subject. `CFB_SUBJECT_CMD` (JSON id -> argv) overrides, for tests."""
    override = os.environ.get("CFB_SUBJECT_CMD")
    if override:
        m = json.loads(override)
        if subject in m:
            return list(m[subject])
    return [str(binary_path(subject, build))]


NATIVE_SUFFIX = "@native"


def native_label(subject: str) -> str:
    """Label carried by every `target-cpu=native` row in raw data and tables."""
    return f"{subject}{NATIVE_SUFFIX}"


def split_label(label: str) -> tuple[str, str]:
    """`cf@native` -> (`cf`, `native`); `zlib` -> (`zlib`, `release`)."""
    if label.endswith(NATIVE_SUFFIX):
        return label[: -len(NATIVE_SUFFIX)], "native"
    return label, "release"
