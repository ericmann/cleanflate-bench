"""zlib-rs status-quo context from public APIs (SPEC 3.9). Context, not a head-to-head comparison."""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from cfbench import env, provenance, rawio

REPO = "trifectatechfoundation/zlib-rs"
CRATES = ["zlib-rs", "libz-rs-sys"]
GITHUB = "https://api.github.com"
CRATES_IO = "https://crates.io/api/v1/crates"
COLUMNS = ["fact", "value", "source_url", "fetched_at"]
PENDING = "no context run; run `python -m cfbench.effort.context` with network access"
SCOPE_NOTE = (
    "Context, not a head-to-head comparison. zlib-rs is a full zlib replacement: complete API and C "
    "ABI, compression as well as decompression, SIMD code paths, and performance parity with zlib-ng "
    "as a goal. cleanflate (this repo's subject) only decompresses, in safe Rust, without SIMD or a "
    "C ABI, and was built in three Foundry rounds; the two efforts have different scopes."
)
_LAST = re.compile(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"')


def last_page(link_header: str | None) -> int | None:
    """The page number of `rel="last"` in a GitHub `Link` header, or None when there is no Link."""
    if not link_header:
        return None
    m = _LAST.search(link_header)
    return int(m.group(1)) if m else None


def open_url(req: urllib.request.Request, timeout: int):
    """The single network call (replaced in tests)."""
    return urllib.request.urlopen(req, timeout=timeout)


def http_fetch(url: str) -> tuple[dict, str]:
    """GET with the project User-Agent; `GITHUB_TOKEN` (never stored) authorises GitHub calls."""
    headers = {"User-Agent": "cleanflate-bench", "Accept": "application/json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(GITHUB):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with open_url(req, 60) as r:
        return {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8")


def _json(fetch, url: str):
    headers, body = fetch(url)
    return headers, json.loads(body)


def count_via_last_page(fetch, url: str) -> int:
    """Item count of a paginated list requested with per_page=1: the last page number."""
    headers, body = _json(fetch, url)
    page = last_page(headers.get("link"))
    return page if page is not None else len(body)


def releases(fetch, repo: str, max_pages: int = 20) -> list[dict]:
    out = []
    for page in range(1, max_pages + 1):
        _h, body = _json(fetch, f"{GITHUB}/repos/{repo}/releases?per_page=100&page={page}")
        out += [{"tag": r["tag_name"], "published_at": r["published_at"]} for r in body]
        if len(body) < 100:
            break
    return sorted(out, key=lambda r: r["published_at"] or "")


def crate_versions(fetch, name: str) -> list[dict]:
    _h, body = _json(fetch, f"{CRATES_IO}/{name}")
    return sorted(
        (
            {"num": v["num"], "created_at": v["created_at"], "yanked": v["yanked"]}
            for v in body["versions"]
        ),
        key=lambda v: v["created_at"],
    )


def collect(fetch=http_fetch, repo: str = REPO) -> dict:
    _h, info = _json(fetch, f"{GITHUB}/repos/{repo}")
    commit_url = f"{GITHUB}/repos/{repo}/commits?per_page=1"
    commit_count = count_via_last_page(fetch, commit_url)
    _h, oldest = _json(fetch, f"{commit_url}&page={commit_count}")
    first = oldest[0]
    contributors = count_via_last_page(
        fetch, f"{GITHUB}/repos/{repo}/contributors?per_page=1&anon=1"
    )
    return {
        "kind": "context",
        "repo": repo,
        "repo_info": {"created_at": info["created_at"], "default_branch": info["default_branch"]},
        "commit_count": commit_count,
        "first_commit": {"sha": first["sha"], "date": first["commit"]["committer"]["date"]},
        "contributor_count": contributors,
        "releases": releases(fetch, repo),
        "crates": {name: crate_versions(fetch, name) for name in CRATES},
        "sources": {
            "repo": f"{GITHUB}/repos/{repo}",
            "commits": commit_url,
            "contributors": f"{GITHUB}/repos/{repo}/contributors?per_page=1&anon=1",
            "releases": f"{GITHUB}/repos/{repo}/releases",
            "crates": {name: f"{CRATES_IO}/{name}" for name in CRATES},
        },
    }


def table_rows(payload: dict, fetched_at: str) -> list[dict]:
    src = payload["sources"]
    rel = payload["releases"]

    def row(fact: str, value, url: str) -> dict:
        return {"fact": fact, "value": value, "source_url": url, "fetched_at": fetched_at}

    rows = [
        row("repo_created_at", payload["repo_info"]["created_at"], src["repo"]),
        row("first_commit_date", payload["first_commit"]["date"], src["commits"]),
        row("first_commit_sha", payload["first_commit"]["sha"], src["commits"]),
        row("commit_count", payload["commit_count"], src["commits"]),
        row(
            "contributor_count_including_anonymous",
            payload["contributor_count"],
            src["contributors"],
        ),
    ]
    if rel:
        rows.append(
            row(
                "first_github_release",
                f"{rel[0]['tag']} ({rel[0]['published_at']})",
                src["releases"],
            )
        )
        rows.append(
            row(
                "latest_github_release",
                f"{rel[-1]['tag']} ({rel[-1]['published_at']})",
                src["releases"],
            )
        )
    for name, versions in payload["crates"].items():
        url = src["crates"][name]
        if versions:
            v = versions[0]
            rows.append(
                row(f"first_published_version_{name}", f"{v['num']} ({v['created_at']})", url)
            )
            rows.append(
                row(
                    f"latest_published_version_{name}",
                    f"{versions[-1]['num']} ({versions[-1]['created_at']})",
                    url,
                )
            )
        stable = [v for v in versions if v["num"].split(".")[0] not in ("0",)]
        rows.append(
            row(
                f"stable_1_0_release_{name}",
                f"{stable[0]['num']} ({stable[0]['created_at']})"
                if stable
                else "none: no 1.0 or later version published as of the fetch date",
                url,
            )
        )
    rows.append(row("scope_note", SCOPE_NOTE, "SPEC 3.9"))
    return rows


def derive() -> None:
    files = rawio.list_raw("effort", machine="any", kind="context")
    script = "cfbench.effort.context"
    if not files:
        provenance.write_table(
            "zlibrs_context", COLUMNS, [], script=script, raw_files=[], pending=PENDING
        )
        return
    doc = rawio.load_raw(files[-1])
    provenance.write_table(
        "zlibrs_context",
        COLUMNS,
        table_rows(doc["payload"], doc["timestamp"]),
        script=script,
        raw_files=[files[-1]],
    )


def main() -> int:
    try:
        payload = collect()
    except OSError as e:
        print(f"error: cannot reach the APIs: {e}", file=sys.stderr)
        return 1
    path: Path = rawio.write_raw(
        "effort",
        payload,
        machine="any",
        profile="full",
        script="cfbench.effort.context",
        environment=env.capture_environment(),
    )
    derive()
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
