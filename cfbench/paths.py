"""Repository path roots. The one place they are spelled."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
THIRD_PARTY = ROOT / "third_party"
BUILD = ROOT / "build"
DATA = ROOT / "data"
RAW = DATA / "raw"
SMOKE = DATA / "smoke"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
