"""JPlag on the same-language pairs (SPEC 3.8). Cross-language pairs are not applicable."""

import json
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from cfbench import config, decomp_paths, download, env, paths, rawio, sources, tools
from cfbench.similarity import pairs

NOT_APPLICABLE = "not applicable (cross-language)"
SUFFIXES = {"rust": ".rs", "c": ".c,.h"}
JPLAG_LANGUAGE = {"rust": "rust", "c": "c"}


def spec() -> dict:
    return config.load_toml("tools.toml")["jplag"]


def jar_path() -> Path:
    return tools.tools_root() / f"jplag-{spec()['version']}.jar"


def work_root() -> Path:
    return paths.THIRD_PARTY / "jplag-work"


def ensure_jar() -> Path:
    s = spec()
    dest = jar_path()
    if not dest.exists():
        downloaded = download.fetch(s["url"], s["sha256"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(downloaded, dest)
    elif download.sha256_file(dest) != s["sha256"]:
        raise download.DownloadError(f"{dest}: SHA-256 differs from config/tools.toml")
    return dest


def java_major(version_output: str) -> int | None:
    """Major version from `java -version` text (`"21.0.1"` or the old `"1.8.0_x"` style)."""
    m = re.search(r'version "(\d+)(?:\.(\d+))?', version_output)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2)) if major == 1 and m.group(2) else major


def _java_version(java: str) -> tuple[int | None, str]:
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, check=False)
    except OSError as e:
        return None, str(e)
    text = out.stderr or out.stdout
    return java_major(text), text.strip().splitlines()[0] if text.strip() else ""


def jre_dir() -> Path:
    return tools.tools_root() / f"jre-{spec()['min_java']}"


def ensure_jre() -> Path:
    """The pinned Temurin JRE for this platform, downloaded and extracted on first use."""
    key = f"{platform.system()}-{platform.machine()}"
    entry = spec()["jre"].get(key)
    if entry is None:
        raise RuntimeError(f"no pinned JRE for {key}")
    dest = jre_dir()
    found = sorted(dest.glob("**/bin/java")) if dest.exists() else []
    if not found:
        tarball = download.fetch(entry["url"], entry["sha256"])
        download.extract(tarball, dest)
        found = sorted(dest.glob("**/bin/java"))
    if not found:
        raise RuntimeError(f"no bin/java under {dest}")
    return found[0]


def ensure_java() -> tuple[str, dict]:
    """A java executable of at least `min_java`, and a description of where it came from."""
    need = spec()["min_java"]
    major, line = _java_version("java")
    if major is not None and major >= need:
        return "java", {"source": "PATH", "version": line, "major": major}
    jre = ensure_jre()
    major, line = _java_version(str(jre))
    if major is None or major < need:
        raise RuntimeError(f"pinned JRE {jre} reports Java {major}, need {need}")
    return str(jre), {
        "source": "pinned Temurin JRE",
        "version": line,
        "major": major,
        "path_java": _java_version("java")[1],
    }


def parse_languages(help_text: str) -> list[str]:
    """Language names from the `Languages:` section at the end of `jplag --help`."""
    out, in_langs = [], False
    for line in help_text.splitlines():
        if line.strip() == "Languages:":
            in_langs = True
        elif in_langs and line.startswith("  ") and line.strip():
            out.append(line.strip())
        elif in_langs and line.strip():
            break
    return out


def verify(java: str, jar: Path) -> dict:
    """List the languages of the installed JPlag and report Rust and C support."""
    res = subprocess.run(
        [java, "-jar", str(jar), "--help"], capture_output=True, text=True, check=False
    )
    langs = parse_languages(res.stdout + res.stderr)
    return {
        "languages": langs,
        "rust": "rust" in langs,
        "c": "c" in langs,
        "pinned_version": spec()["version"],
    }


def parse_comparison(text: str) -> dict:
    d = json.loads(text)
    sims = d["similarities"]
    return {
        "avg": sims["AVG"],
        "max": sims["MAX"],
        "max_length": sims.get("MAXIMUM_LENGTH"),
        "longest_match": sims.get("LONGEST_MATCH"),
        "matches": len(d["matches"]),
    }


def parse_result_archive(archive: Path) -> dict:
    """Metrics of the single comparison in a .jplag result archive, plus run information."""
    with zipfile.ZipFile(archive) as z:
        comp = [n for n in z.namelist() if n.startswith("comparisons/") and n.endswith(".json")]
        if len(comp) != 1:
            raise RuntimeError(f"expected one comparison in {archive}, found {len(comp)}")
        out = parse_comparison(z.read(comp[0]).decode())
        run = json.loads(z.read("runInformation.json"))
        opts = json.loads(z.read("options.json"))
    v = run["version"]
    out["jplag_version"] = f"{v['major']}.{v['minor']}.{v['patch']}"
    out["min_tokens"] = opts["minimumTokenMatch"]
    return out


def stage_submission(subject: str, dest: Path) -> int:
    """Copy a subject's decompression-path files into dest, keeping relative paths."""
    root = sources.source_root(subject)
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in decomp_paths.files(subject):
        rel = f.relative_to(root)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, target)
        n += 1
    return n


def classify(pair: dict) -> dict:
    """Same-language pairs run through JPlag; cross-language pairs are marked not applicable."""
    if pair["cross_language"]:
        return {**pair, "status": NOT_APPLICABLE}
    return {**pair, "status": "pending"}


def all_pairs(cfg: dict) -> list[dict]:
    plist = pairs.load_pairs(cfg, reference=True)
    for p in cfg["similarity"]["context_pairs"]:
        plist.append(
            {
                "left": p["left"],
                "right": p["right"],
                "role": p["role"],
                "cross_language": pairs.LANGUAGE[p["left"]] != pairs.LANGUAGE[p["right"]],
            }
        )
    return plist


def run_pair(java: str, jar: Path, pair: dict) -> dict:
    lang = pairs.LANGUAGE[pair["left"]]
    work = work_root() / f"{pair['left']}-{pair['right']}"
    if work.exists():
        shutil.rmtree(work)
    subs = work / "submissions"
    counts = {s: stage_submission(s, subs / s) for s in (pair["left"], pair["right"])}
    archive = work / "result.jplag"
    cmd = [
        java, "-jar", str(jar), "-M", "RUN", "-l", JPLAG_LANGUAGE[lang], "-p", SUFFIXES[lang],
        "-r", str(work / "result"), "--overwrite", "--cluster-skip", str(subs),
    ]  # fmt: skip
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not archive.exists():
        return {
            **pair,
            "status": "error",
            "error": (res.stderr or res.stdout)[-300:],
            "files": counts,
        }
    out = parse_result_archive(archive)
    return {**pair, "status": "ok", "language": lang, "files": counts, **out}


def payload(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    gaps: list = []
    jar = ensure_jar()
    plist = all_pairs(cfg)
    try:
        java, java_info = ensure_java()
        info = verify(java, jar)
    except Exception as e:  # noqa: BLE001 - tool-gap protocol
        gaps.append(
            {
                "tool": "jplag",
                "version": spec()["version"],
                "command": f"java -jar {jar}",
                "error": str(e),
            }
        )
        return {
            "kind": "jplag",
            "tool": {"jplag": spec()["version"]},
            "pairs": [
                classify(p) if p["cross_language"] else {**p, "status": "unavailable"}
                for p in plist
            ],
            "tool_gaps": gaps,
        }
    results = []
    for p in plist:
        lang = pairs.LANGUAGE[p["left"]]
        if p["cross_language"]:
            results.append(classify(p))
        elif not info.get(lang):
            gaps.append(
                {"tool": "jplag", "version": spec()["version"], "command": "--help",
                 "error": f"language {lang} not listed"}
            )  # fmt: skip
            results.append({**p, "status": "unavailable"})
        else:
            results.append(run_pair(java, jar, p))
    return {
        "kind": "jplag",
        "tool": {"jplag": spec()["version"], "java": java_info, **info},
        "pairs": results,
        "tool_gaps": gaps,
    }


def main() -> int:
    data = payload()
    path = rawio.write_raw(
        "similarity",
        data,
        machine="any",
        profile="full",
        script="cfbench.similarity.jplag",
        environment=env.capture_environment(),
    )
    print(path)
    for g in data["tool_gaps"]:
        print(f"tool gap: {g['tool']}: {g['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
