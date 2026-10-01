"""Content features of every corpus workload stream via infgen (SPEC 3.4).

Workloads are byte-identical across machines (the manifest pins them), so the raw document is
written for machine `any` and records the SHA-256 of the workload manifest. Token features do not
depend on the framing, so they are computed on the raw-framed stream and copied to the zlib and
gzip rows; only the `ratio` is taken from each framing's own stream size (wrapper bytes differ).
"""

import hashlib
import sys

from cfbench import config, env, provenance, rawio, workloads
from cfbench.content import infgen

CATEGORY = "content"
KIND = "content-features"
ANALYSED = "raw"
LEN_COLS = [f"len_frac_{b.replace('-', '_')}" for b in infgen.LEN_BINS]
DIST_COLS = [f"dist_frac_{b.replace('-', '_')}" for b in infgen.DIST_BINS]
COLUMNS = [
    "workload",
    "corpus",
    "level",
    "framing",
    "framing_analysed",
    "literal_fraction",
    "dist1_fraction",
    "dist2_7_fraction",
    "overlap_fraction",
    "mean_match_len",
    "blocks_stored",
    "blocks_fixed",
    "blocks_dynamic",
    "ratio",
    *LEN_COLS,
    *DIST_COLS,
]
PENDING = "no content run; run make content-features"


def manifest_sha256() -> str:
    return hashlib.sha256(workloads.manifest_path().read_bytes()).hexdigest()


def corpus_workloads(cfg: dict) -> list:
    """The raw-framed corpus workloads (tiny inputs are excluded)."""
    return [
        w for w in workloads.list_workloads(cfg) if w.corpus != "tiny" and w.framing == ANALYSED
    ]


def analyse(cfg: dict | None = None, stats_fn=None) -> dict:
    """Run infgen over every corpus workload (raw framing) and return the raw payload."""
    cfg = cfg or config.load_config("full")
    stats_fn = stats_fn or infgen.stats
    manifest = workloads.load_manifest() or {"entries": []}
    sizes = {(e["id"], e["level"], e["framing"]): e["len"] for e in manifest["entries"]}
    entries = []
    for w in corpus_workloads(cfg):
        s = stats_fn(w.path, ANALYSED)
        entries.append(
            {
                "workload": w.id,
                "corpus": w.corpus,
                "level": w.level,
                "framing_analysed": ANALYSED,
                "orig_len": w.orig_len,
                "stream_sizes": {f: sizes.get((w.id, w.level, f)) for f in cfg["perf"]["framings"]},
                "stats": s,
            }
        )
    return {
        "kind": KIND,
        "tool": {"infgen": infgen.spec()["commit"]},
        "workload_manifest_sha256": manifest_sha256(),
        "entries": entries,
    }


def table_rows(payload: dict, framings: list[str]) -> list[dict]:
    """One row per workload, level and framing; token features copied from the analysed framing."""
    rows = []
    for e in payload["entries"]:
        s = e["stats"]
        m = s["matches"]
        for f in framings:
            size = e["stream_sizes"].get(f)
            row = {
                "workload": e["workload"],
                "corpus": e["corpus"],
                "level": e["level"],
                "framing": f,
                "framing_analysed": e["framing_analysed"],
                "literal_fraction": s["literal_fraction"],
                "dist1_fraction": s["dist1_fraction"],
                "dist2_7_fraction": s["dist2_7_fraction"],
                "overlap_fraction": s["overlap_fraction"],
                "mean_match_len": s["mean_match_len"],
                "blocks_stored": s["blocks"]["stored"],
                "blocks_fixed": s["blocks"]["fixed"],
                "blocks_dynamic": s["blocks"]["dynamic"],
                "ratio": size / e["orig_len"] if size and e["orig_len"] else s["ratio"],
            }
            for col, b in zip(LEN_COLS, infgen.LEN_BINS, strict=True):
                row[col] = s["match_len_hist"][b] / m if m else None
            for col, b in zip(DIST_COLS, infgen.DIST_BINS, strict=True):
                row[col] = s["match_dist_hist"][b] / m if m else None
            rows.append(row)
    return rows


def derive(cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config.load_config("full")
    script = "cfbench.content.features"
    files = rawio.list_raw(CATEGORY, machine="any", kind=KIND)
    if not files:
        provenance.write_table(
            "content_features", COLUMNS, [], script=script, raw_files=[], pending=PENDING
        )
        return []
    doc = rawio.load_raw(files[-1])
    rows = table_rows(doc["payload"], cfg["perf"]["framings"])
    provenance.write_table("content_features", COLUMNS, rows, script=script, raw_files=[files[-1]])
    return rows


def run() -> None:
    cfg = config.load_config("full")
    payload = analyse(cfg)
    path = rawio.write_raw(
        CATEGORY,
        payload,
        machine="any",
        profile="full",
        script="cfbench.content.features",
        environment=env.capture_environment(),
    )
    print(path)
    derive(cfg)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "run"
    if cmd == "run":
        run()
    elif cmd == "derive":
        derive()
    else:
        print("usage: cfbench.content.features [run|derive]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
