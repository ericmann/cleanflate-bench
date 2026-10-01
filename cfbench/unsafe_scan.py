"""Count `unsafe` constructs in a Rust crate, ignoring comments and string literals."""

import re
from pathlib import Path

EXCLUDED_DIRS = {"tests", "benches", "examples"}
COUNT_KEYS = ["unsafe_blocks", "unsafe_fns", "unsafe_impls", "unsafe_traits", "target_feature"]

_BLOCK = re.compile(r"\bunsafe\s*\{")
_FN = re.compile(r"\bunsafe\s+(?:const\s+)?(?:extern\s*(?:\"\"\s*)?)?fn\b")
_IMPL = re.compile(r"\bunsafe\s+impl\b")
_TRAIT = re.compile(r"\bunsafe\s+trait\b")
_TARGET_FEATURE = re.compile(r"#\s*\[\s*target_feature\b")
_FORBID = re.compile(r"#!\[\s*forbid\s*\([^\]]*\bunsafe_code\b")
_DENY = re.compile(r"#!\[\s*deny\s*\([^\]]*\bunsafe_code\b")


def strip_comments_and_strings(src: str) -> str:
    """Blank out comments; keep string literals as empty `""`. Newlines are preserved."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i : i + 2]
        if two == "//":
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif two == "/*":
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    if src[i] == "\n":
                        out.append("\n")
                    i += 1
        elif c == "r" and re.match(r'r#*"', src[i:]) and (i == 0 or not src[i - 1].isalnum()):
            m = re.match(r'r(#*)"', src[i:])
            hashes = m.group(1)
            end = src.find('"' + hashes, i + m.end())
            end = n if end < 0 else end + 1 + len(hashes)
            out.append('""')
            out.append("\n" * src.count("\n", i, end))
            i = end
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            out.append('""')
            out.append("\n" * src.count("\n", i, min(j, n)))
            i = j + 1
        elif c == "'":
            # a char literal ('x', '\n', '\u{..}') versus a lifetime ('a)
            m = re.match(r"'(?:\\.[^']*|[^\\'])'", src[i:])
            if m:
                out.append("''")
                i += m.end()
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def count_text(src: str) -> dict:
    s = strip_comments_and_strings(src)
    return {
        "unsafe_blocks": len(_BLOCK.findall(s)),
        "unsafe_fns": len(_FN.findall(s)),
        "unsafe_impls": len(_IMPL.findall(s)),
        "unsafe_traits": len(_TRAIT.findall(s)),
        "target_feature": len(_TARGET_FEATURE.findall(s)),
    }


def scan_crate(root: Path) -> dict:
    root = Path(root)
    files = {}
    for p in sorted(root.rglob("*.rs")):
        rel = p.relative_to(root)
        if rel.parts[0] in EXCLUDED_DIRS:
            continue
        files[rel.as_posix()] = count_text(p.read_text(encoding="utf-8", errors="replace"))
    totals = {k: sum(f[k] for f in files.values()) for k in COUNT_KEYS}
    lib = root / "src" / "lib.rs"
    lib_src = strip_comments_and_strings(lib.read_text(encoding="utf-8")) if lib.exists() else ""
    return {
        "files": files,
        "totals": totals,
        "forbid_unsafe_code": bool(_FORBID.search(lib_src)),
        "deny_unsafe_code": bool(_DENY.search(lib_src)),
    }
