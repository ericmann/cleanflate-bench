"""A stand-in subject binary for orchestrator tests.

Usage: fake_subject.py [--framings raw,zlib] [--fail] info | bench --cell PATH
"""

import json
import sys


def main(argv):
    framings = ["raw", "zlib", "gzip"]
    fail = False
    while argv and argv[0].startswith("--") and argv[0] != "--cell":
        if argv[0] == "--framings":
            framings = argv[1].split(",")
            argv = argv[2:]
        elif argv[0] == "--fail":
            fail = True
            argv = argv[1:]
        else:
            break
    cmd = argv[0]
    if cmd == "info":
        print(
            json.dumps(
                {
                    "id": "fake",
                    "impl_version": "0",
                    "framings": framings,
                    "modes": ["oneshot", "stream"],
                    "checksums": [],
                    "dictionary": False,
                    "output_limit": "caller",
                }
            )
        )
        return 0
    if cmd == "bench":
        if fail:
            print("boom", file=sys.stderr)
            return 3
        with open(argv[2]) as f:
            cell = json.load(f)
        n = int(cell["min_samples"])
        print(
            json.dumps(
                {
                    "ok": True,
                    "error": None,
                    "input_bytes": 10,
                    "output_bytes": 20,
                    "iters_per_sample": 1,
                    "samples_ns": [100.0 + i for i in range(n)],
                    "peak_heap_bytes": 1,
                    "alloc_calls": 1,
                }
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
