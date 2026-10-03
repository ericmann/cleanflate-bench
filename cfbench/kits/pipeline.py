"""The framing every kit shares: the pipeline is the subject, cleanflate is the worked example.

Rename the pipeline by editing `PIPELINE_NAME` only; every kit reads it from here.
"""

from dataclasses import dataclass

from cfbench import config

PIPELINE_NAME = "Foundry"
EXAMPLE = "cleanflate"
LEGACY = "zlib"
NOTES_FILE = "session_notes.toml"


def thesis() -> str:
    return (
        f"{PIPELINE_NAME} is an agentic clean-room pipeline. It produced a functionally equivalent, "
        f"memory-safe replacement for a legacy C library from RFCs alone, under mechanically enforced "
        f"isolation from prior art. {EXAMPLE} (`cf`), a decompress-only safe-Rust replacement for "
        f"{LEGACY}'s inflate, is the worked example that supplies the evidence. Every claim below is "
        f"about the pipeline and is tested on that one example."
    )


@dataclass(frozen=True)
class Category:
    key: str
    title: str
    question: str


CATEGORIES = [
    Category("equivalence", "Equivalence", f"Does {EXAMPLE} decode exactly what {LEGACY} decodes?"),
    Category("safety", "Safety", "Is the replacement memory-safe by construction?"),
    Category("clean_room", "Clean-room", "Was the build isolated from prior art, and does the code show it?"),
    Category("effort", "Effort", "What did the build take in time, money and human help?"),
    Category("viability", "Viability", "Is the replacement fast enough to matter, on both machines?"),
    Category("iteration", "Iteration", f"Did {PIPELINE_NAME}'s later rounds improve it?"),
]  # fmt: skip
CATEGORY_TITLES = {c.key: c.title for c in CATEGORIES}


@dataclass(frozen=True)
class Note:
    id: str
    machine: str
    stages: tuple[str, ...]
    text: str
    corroboration: str


def notes() -> list[Note]:
    """Operator notes from config/session_notes.toml, in file order."""
    doc = config.load_toml(NOTES_FILE)
    return [Note(n["id"], n["machine"], tuple(n["stages"]), n["text"], n.get("corroboration", ""))
            for n in doc.get("notes", [])]  # fmt: skip


def note(note_id: str) -> Note | None:
    return next((n for n in notes() if n.id == note_id), None)


def note_text(note_id: str) -> str:
    """`Operator note: <text> (<corroboration>).`, or '' when the note is absent."""
    n = note(note_id)
    if n is None:
        return ""
    extra = f" Corroboration: {n.corroboration}." if n.corroboration else ""
    return f"Operator note (`config/{NOTES_FILE}`, `{n.id}`): {n.text}{extra}"


def not_run_reason(machine: str, table: str) -> str | None:
    """The recorded reason a table was deliberately not measured on a machine, if any."""
    for e in config.load_toml(NOTES_FILE).get("not_run", []):
        if e["machine"] == machine and table in e["tables"]:
            return e["reason"]
    return None
