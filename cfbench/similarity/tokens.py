"""Tree-sitter tokenisation of Rust and C into a shared, normalised vocabulary.

Leaf nodes map to token classes (see docs/methods/similarity.md for the full table).
Comments are excluded from the token stream and returned separately.
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import tree_sitter_c
import tree_sitter_rust
from tree_sitter import Language, Node, Parser

LANGUAGES = {".rs": "rust", ".c": "c", ".h": "c"}

COMMENT_TYPES = {"comment", "line_comment", "block_comment"}
STRING_TYPES = {
    "string_literal",
    "raw_string_literal",
    "system_lib_string",
    "concatenated_string",
}
CHAR_TYPES = {"char_literal"}
NUM_TYPES = {"integer_literal", "float_literal", "number_literal"}
ID_TYPES = {
    "identifier",
    "type_identifier",
    "field_identifier",
    "shorthand_field_identifier",
    "statement_identifier",
    "label",
    "metavariable",
}
TYPE_TYPES = {"primitive_type"}
SKIP_LEAVES = {"preproc_arg"}

KEYWORD_CLASS = {
    "if": "if",
    "else": "else",
    "for": "LOOP",
    "while": "LOOP",
    "loop": "LOOP",
    "do": "LOOP",
    "match": "SWITCH",
    "switch": "SWITCH",
    "return": "return",
    "break": "break",
    "continue": "continue",
    "fn": "FN",
    "struct": "TYPEDEF",
    "enum": "TYPEDEF",
    "union": "TYPEDEF",
    "type": "TYPEDEF",
    "typedef": "TYPEDEF",
}

# Token kinds whose text is replaced by the kind name in the normalised stream.
ABSTRACTED = {"ID", "NUM", "STR", "CHAR", "TYPE"}


@dataclass(frozen=True, slots=True)
class Token:
    kind: str  # ID NUM STR CHAR TYPE CLASS or TOK (literal operator, punctuation, keyword)
    text: str
    line: int

    @property
    def norm(self) -> str:
        """The form used for n-grams: identifiers, literals and primitive types abstracted."""
        return self.kind if self.kind in ABSTRACTED else self.text


def language_for(path: Path | str) -> str:
    ext = Path(path).suffix
    if ext not in LANGUAGES:
        raise ValueError(f"cannot tokenize {path}: unknown extension {ext!r}")
    return LANGUAGES[ext]


@cache
def _parser(language: str) -> Parser:
    lang = {"rust": tree_sitter_rust.language, "c": tree_sitter_c.language}[language]()
    return Parser(Language(lang))


def _leaf_token(node: Node, language: str) -> Token | None:
    t = node.type
    line = node.start_point[0] + 1
    text = node.text.decode("utf-8", errors="replace")
    if t in SKIP_LEAVES:
        return None
    if t in STRING_TYPES:
        return Token("STR", text, line)
    if t in CHAR_TYPES:
        return Token("CHAR", text, line)
    if t in NUM_TYPES:
        return Token("NUM", text, line)
    if t in ID_TYPES:
        return Token("ID", text, line)
    if t in TYPE_TYPES:
        return Token("TYPE", text, line)
    if t in KEYWORD_CLASS and not node.is_named:
        parent = node.parent.type if node.parent else ""
        # `impl Trait for Type` and `for<'a>` are not loops
        if t == "for" and language == "rust" and parent != "for_expression":
            return Token("TOK", text, line)
        return Token("CLASS", KEYWORD_CLASS[t], line)
    return Token("TOK", text, line)


def _walk(root: Node, language: str, toks: list[Token], comments: list[tuple[int, str]]) -> None:
    """Depth-first, in source order, with an explicit stack (deep else-if chains overflow recursion)."""
    stack = [root]
    while stack:
        node = stack.pop()
        t = node.type
        if t in COMMENT_TYPES:
            comments.append((node.start_point[0] + 1, node.text.decode("utf-8", errors="replace")))
            continue
        atomic = t in STRING_TYPES or t in CHAR_TYPES
        if language == "c" and t == "function_definition":
            toks.append(Token("CLASS", "FN", node.start_point[0] + 1))
        if atomic or node.child_count == 0:
            tok = _leaf_token(node, language)
            if tok is not None:
                toks.append(tok)
            continue
        stack.extend(reversed(node.children))


def _parse(path: Path | str, language: str | None) -> tuple[list[Token], list[tuple[int, str]]]:
    language = language or language_for(path)
    src = Path(path).read_bytes()
    tree = _parser(language).parse(src)
    toks: list[Token] = []
    comments: list[tuple[int, str]] = []
    _walk(tree.root_node, language, toks, comments)
    return toks, comments


def tokenize(path: Path | str, language: str | None = None) -> list[Token]:
    return _parse(path, language)[0]


def comments(path: Path | str, language: str | None = None) -> list[tuple[int, str]]:
    return _parse(path, language)[1]
