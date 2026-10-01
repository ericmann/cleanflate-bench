"""Top-k longest matching token fragments per pair, with persistent human verdicts (SPEC 3.8).

Method: hash-of-window. Every window of `ngram_max` consecutive normalised tokens of the right
subject is indexed; each left window found in the index yields a (left file, position, right file,
position) match. Matches on the same diagonal that are consecutive are merged into one maximal run,
whose token length is the number of merged windows plus `ngram_max - 1`. Runs are ranked by length,
ties broken by left file, left line, right file and right line. Fragments never cross a file
boundary because windows are built per file. A window that occurs more than
`similarity.max_window_occurrences` times in either subject is treated as boilerplate (repeated
braces, constant-table rows) and skipped, because every left occurrence would pair with every right
occurrence and the match set grows quadratically (a first uncapped run took nearly seven minutes);
the number of skipped distinct windows is recorded with each pair. Controls (negative and positive pairs) are run through
the same code so the test pairs can be read against them.
"""

import hashlib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cfbench import config, decomp_paths, env, paths, provenance, rawio, sources
from cfbench.similarity import pairs
from cfbench.similarity.run import subject_files, tool_versions
from cfbench.similarity.tokens import Token, tokenize

VERDICTS = ("RFC-forced", "idiomatic-inevitable", "suspicious")
EXCERPT_LINES = 40
COLUMNS = [
    "rank",
    "fragment_id",
    "tokens",
    "left_file",
    "left_lines",
    "right_file",
    "right_lines",
    "verdict",
    "note",
]


@dataclass(frozen=True)
class Fragment:
    tokens: int
    left_file: str
    left_start: int
    left_end: int
    right_file: str
    right_start: int
    right_end: int
    run: tuple  # the normalised tokens of the run


def fragment_id(frag: Fragment) -> str:
    """First 12 hex characters of SHA-256 over the normalised run and both file paths."""
    h = hashlib.sha256()
    h.update("\x1f".join(frag.run).encode())
    h.update(f"\x00{frag.left_file}\x00{frag.right_file}".encode())
    return h.hexdigest()[:12]


def find_fragments(
    left: dict[str, list[Token]],
    right: dict[str, list[Token]],
    min_len: int,
    top_k: int | None = None,
    max_occurrences: int | None = None,
) -> tuple[list[Fragment], int]:
    """Maximal matching runs of at least `min_len` normalised tokens, longest first.

    Returns (fragments, number of distinct boilerplate windows skipped).
    """
    r_norm = {f: [t.norm for t in toks] for f, toks in right.items()}
    l_norm = {f: [t.norm for t in toks] for f, toks in left.items()}
    index: dict[tuple, list[tuple[str, int]]] = {}
    for f, norms in r_norm.items():
        for j in range(len(norms) - min_len + 1):
            index.setdefault(tuple(norms[j : j + min_len]), []).append((f, j))
    left_count: dict[tuple, int] = {}
    for norms in l_norm.values():
        for i in range(len(norms) - min_len + 1):
            w = tuple(norms[i : i + min_len])
            left_count[w] = left_count.get(w, 0) + 1
    skipped: set[tuple] = set()
    matches: set[tuple[str, int, str, int]] = set()
    for f, norms in l_norm.items():
        for i in range(len(norms) - min_len + 1):
            w = tuple(norms[i : i + min_len])
            hits = index.get(w)
            if not hits:
                continue
            if max_occurrences is not None and (
                len(hits) > max_occurrences or left_count[w] > max_occurrences
            ):
                skipped.add(w)
                continue
            for rf, j in hits:
                matches.add((f, i, rf, j))
    frags = []
    for f, i, rf, j in sorted(matches):
        if (f, i - 1, rf, j - 1) in matches:
            continue
        n = 1
        while (f, i + n, rf, j + n) in matches:
            n += 1
        length = n + min_len - 1
        lt, rt = left[f], right[rf]
        frags.append(
            Fragment(
                tokens=length,
                left_file=f,
                left_start=lt[i].line,
                left_end=lt[i + length - 1].line,
                right_file=rf,
                right_start=rt[j].line,
                right_end=rt[j + length - 1].line,
                run=tuple(l_norm[f][i : i + length]),
            )
        )
    frags.sort(key=lambda x: (-x.tokens, x.left_file, x.left_start, x.right_file, x.right_start))
    return (frags[:top_k] if top_k else frags), len(skipped)


def parse_verdicts(text: str) -> dict[str, dict[str, dict]]:
    """{pair: {fragment_id: {verdict, note}}}; any verdict outside the SPEC values raises."""
    data = tomllib.loads(text)
    for pair, entries in data.items():
        for fid, v in entries.items():
            if v.get("verdict") not in VERDICTS:
                raise ValueError(f"[{pair}] {fid}: verdict {v.get('verdict')!r} not in {VERDICTS}")
    return data


def load_verdicts() -> dict:
    return parse_verdicts((paths.CONFIG / "similarity_verdicts.toml").read_text(encoding="utf-8"))


def merge_verdicts(rows: list[dict], stored: dict) -> list[dict]:
    """Attach stored verdicts and notes by fragment id; unknown ids stay empty."""
    out = []
    for r in rows:
        v = stored.get(r["fragment_id"], {})
        out.append({**r, "verdict": v.get("verdict", ""), "note": v.get("note", "")})
    return out


def _lines(a: int, b: int) -> str:
    return f"{a}-{b}"


def _excerpt(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[start - 1 : end]
    return "\n".join(lines[:EXCERPT_LINES])


def pair_rows(left: str, right: str, cfg: dict) -> tuple[list[dict], int]:
    """Top-k fragment rows for a pair, with excerpts (no verdicts yet), and skipped windows."""
    min_len = cfg["similarity"]["ngram_max"]
    k = cfg["similarity"]["top_k"]
    cap = cfg["similarity"]["max_window_occurrences"]
    out = {}
    roots = {}
    for subject, bucket in ((left, "l"), (right, "r")):
        root = sources.source_root(subject)
        roots[bucket] = root
        out[bucket] = {
            f.relative_to(root).as_posix(): (f, tokenize(f)) for f in decomp_paths.files(subject)
        }
    lt = {rel: toks for rel, (_p, toks) in out["l"].items()}
    rt = {rel: toks for rel, (_p, toks) in out["r"].items()}
    rows = []
    frags, skipped = find_fragments(lt, rt, min_len, k, cap)
    for rank, fr in enumerate(frags, start=1):
        rows.append(
            {
                "rank": rank,
                "fragment_id": fragment_id(fr),
                "tokens": fr.tokens,
                "left_file": fr.left_file,
                "left_lines": _lines(fr.left_start, fr.left_end),
                "right_file": fr.right_file,
                "right_lines": _lines(fr.right_start, fr.right_end),
                "left_excerpt": _excerpt(out["l"][fr.left_file][0], fr.left_start, fr.left_end),
                "right_excerpt": _excerpt(out["r"][fr.right_file][0], fr.right_start, fr.right_end),
            }
        )
    return rows, skipped


def payload(cfg: dict | None = None) -> dict:
    cfg = cfg or config.load_config("full")
    results = []
    subjects: set[str] = set()
    for p in pairs.load_pairs(cfg):
        subjects |= {p["left"], p["right"]}
        rows, skipped = pair_rows(p["left"], p["right"], cfg)
        results.append({**p, "fragments": rows, "skipped_windows": skipped})
    return {
        "kind": "fragments",
        "min_tokens": cfg["similarity"]["ngram_max"],
        "top_k": cfg["similarity"]["top_k"],
        "max_window_occurrences": cfg["similarity"]["max_window_occurrences"],
        "pairs": results,
        "files": {s: subject_files(s) for s in sorted(subjects)},
        "tools": tool_versions(),
    }


def markdown(pair: dict, rows: list[dict]) -> str:
    out = [f"# Fragments: {pair['left']} vs {pair['right']} ({pair['role']})", ""]
    out.append(
        "Verdicts live in `config/similarity_verdicts.toml` under "
        f"`[{pair['left']}_{pair['right']}]` keyed by fragment id; allowed values: "
        + ", ".join(f"`{v}`" for v in VERDICTS)
        + "."
    )
    out.append("")
    if not rows:
        out.append("No fragments of the minimum length.")
    for r in rows:
        out.append(f"## {r['rank']}. `{r['fragment_id']}` ({r['tokens']} tokens)")
        out.append("")
        out.append(
            f"Verdict: {r['verdict'] or '(none yet)'}" + (f" - {r['note']}" if r["note"] else "")
        )
        out.append("")
        out.append(f"{pair['left']}: `{r['left_file']}` lines {r['left_lines']}")
        out.append("")
        out.append("```")
        out.append(r["left_excerpt"])
        out.append("```")
        out.append("")
        out.append(f"{pair['right']}: `{r['right_file']}` lines {r['right_lines']}")
        out.append("")
        out.append("```")
        out.append(r["right_excerpt"])
        out.append("```")
        out.append("")
    return "\n".join(out)


def derive(doc_path: Path | None = None) -> list[Path]:
    """Write the per-pair tables and review files from the latest raw `fragments` run."""
    files = rawio.list_raw("similarity", machine="any", kind="fragments")
    if doc_path is None and not files:
        return []
    doc_path = doc_path or files[-1]
    doc = rawio.load_raw(doc_path)
    verdicts = load_verdicts()
    out_dir = paths.RESULTS / "similarity_fragments"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for p in doc["payload"]["pairs"]:
        name = f"{p['left']}_{p['right']}"
        rows = merge_verdicts(p["fragments"], verdicts.get(name, {}))
        provenance.write_table(
            f"similarity_fragments_{name}",
            COLUMNS,
            rows,
            script="cfbench.similarity.fragments",
            raw_files=[doc_path],
        )
        md = out_dir / f"{name}.md"
        md.write_text(markdown(p, rows), encoding="utf-8")
        written.append(md)
    return written


def main() -> int:
    data = payload()
    path = rawio.write_raw(
        "similarity",
        data,
        machine="any",
        profile="full",
        script="cfbench.similarity.fragments",
        environment=env.capture_environment(),
    )
    derive(path)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
