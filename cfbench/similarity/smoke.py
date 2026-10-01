"""Smoke similarity run: cf against miniz_oxide's inflate module (quick profile only)."""

import sys

from cfbench import config, env, rawio, sources
from cfbench.similarity import ngram

SMOKE_MACHINE = "any"


def run() -> dict:
    cfg = config.load_config("quick")
    n = cfg["similarity"]["ngram_min"]
    cf_root = sources.source_root("cf") / "src"
    mox_root = sources.source_root("mox") / "src" / "inflate"
    cf_files = sorted(
        p for p in cf_root.rglob("*.rs") if "tests" not in p.relative_to(cf_root).parts
    )
    mox_files = sorted(mox_root.rglob("*.rs"))
    result = ngram.compare(cf_files, mox_files, n)
    return {
        "kind": "similarity_smoke",
        "pair": ["cf", "mox"],
        "n": n,
        "files_a": [p.relative_to(cf_root).as_posix() for p in cf_files],
        "files_b": [p.relative_to(mox_root).as_posix() for p in mox_files],
        **result,
    }


def main() -> int:
    payload = run()
    path = rawio.write_raw(
        "similarity",
        payload,
        machine=SMOKE_MACHINE,
        profile="quick",
        script="cfbench.similarity.smoke",
        environment=env.capture_environment(),
    )
    print(f"cf~mox n={payload['n']} jaccard={payload['jaccard']:.4f} -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
