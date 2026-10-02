# Similarity method: tree-sitter token n-gram Jaccard

This is the documented fallback of SPEC 3.8 ("tree-sitter token n-gram Jaccard, normalized 5-10-grams,
identifiers abstracted"). It is the method used throughout this repo; JPlag, if it can be run, is an
additional method (see later tasks).

## Pipeline

1. Parse each source file with tree-sitter (`tree-sitter-rust` 0.24.2, `tree-sitter-c` 0.24.2,
   `tree-sitter` 0.26.0, pinned through `uv.lock`). Language is chosen by extension: `.rs` is Rust,
   `.c` and `.h` are C.
2. Walk the tree and emit one token per leaf node. Comments never enter the token stream; they are
   returned separately by `tokens.comments`.
3. Normalise each token (`Token.norm`). Identifiers, literals and primitive types are abstracted to
   their class name; everything else keeps its text.
4. Build the set of n-grams (shingles) of the normalised stream per file and take the union over the
   files of a subject. N-grams never span two files.
5. Compare two subjects with Jaccard (`|A and B| / |A or B|`) and containment
   (`|A and B| / min(|A|, |B|)`). Sizes are shingle counts.

## Token vocabulary

| Token kind | Source nodes | Normalised form |
|---|---|---|
| `ID` | `identifier`, `type_identifier`, `field_identifier`, `shorthand_field_identifier`, `statement_identifier`, `label`, `metavariable` | `ID` |
| `NUM` | `integer_literal`, `float_literal`, `number_literal` | `NUM` |
| `STR` | `string_literal`, `raw_string_literal`, `system_lib_string`, `concatenated_string` | `STR` |
| `CHAR` | `char_literal` | `CHAR` |
| `TYPE` | `primitive_type` (`u32`, `int`, `str`, ...) | `TYPE` |
| `CLASS` | keywords, below | the class name |
| `TOK` | operators, punctuation and every other keyword (`let`, `mut`, `const`, `unsafe`, `pub`, `static`, `true`, ...) | the literal text |

Keyword classes shared by both languages:

| Class | Rust | C |
|---|---|---|
| `if` | `if` | `if` |
| `else` | `else` | `else` |
| `LOOP` | `for` (in a `for_expression`), `while`, `loop` | `for`, `while`, `do` |
| `SWITCH` | `match` | `switch` |
| `return` | `return` | `return` |
| `break` | `break` | `break` |
| `continue` | `continue` | `continue` |
| `FN` | the `fn` keyword | synthetic token emitted at the head of every `function_definition` |
| `TYPEDEF` | `struct`, `enum`, `union`, `type` | `struct`, `enum`, `union`, `typedef` |

Notes and limits:

- Rust `for` inside `impl Trait for Type` and `for<'a>` stays a literal `for` token, because it is not a loop.
- C preprocessor macro bodies (`preproc_arg`) are skipped.
- Documentation comments in Rust and block comments in C are comments and are excluded from tokens.
- Two files that tokenise to the same stream are identical for this method regardless of formatting,
  identifier names or literal values. A high score therefore means structural similarity, not copying;
  every high-scoring fragment still needs the human verdict recorded later in the pipeline.
- The vocabulary is a convention of this repo. It makes Rust-to-C comparisons possible but cannot erase
  all language differences (`let`, `mut`, `->`, `::` and `unsafe` exist only on the Rust side), which
  lowers cross-language scores. The negative and positive controls (zrs vs mox, zrs vs zng) calibrate
  this effect.

## Parameters

`[similarity] ngram_min = 5` and `ngram_max = 10` in `config/bench.toml`. The smoke run uses `ngram_min`
only.

## Post-hoc identifier sensitivity analysis

Added 2026-10-02, after the first full similarity run; it is not pre-registered and does not
decide the T1 claim.

The pre-registered identifier metrics (`ident_jaccard`, `ident_match_rate_left`) exclude the names in
`config/rfc_identifiers.txt`. In the first full run the shared-identifier sets of every Rust pair,
controls included, were dominated by names the implementer does not choose: attribute and lint
names (`cfg_attr`, `inline`, `clippy`), std method and macro names (`is_empty`, `enumerate`,
`debug_assert`) and names built only from RFC-defined terms (`length_base`, `dist_extra`,
`litlen_table`). With 330-770 identifiers per subject, a few such names move a pair's position
between the controls by more than the 0.25 "near" band.

`config/identifier_exclusions_posthoc.txt` extends the exclusions by category, never by pair. The
categories are Rust attribute, lint, derive, cfg, std/core trait, macro and method names, and
names made only of RFC 1950/1951/1952 terms plus a generic suffix. Zlib API names and generic task
words are kept, as in the pre-registered list. The extended list is applied to every pair,
controls included, giving `ident_jaccard_filtered` and `ident_match_rate_left_filtered`.

`results/similarity_statement.md` reports the T1 claim on the pre-registered metrics, then a
separate "Post-hoc sensitivity" line. That line repeats the test with the two identifier metrics
replaced by their filtered versions. Both lines appear in RESULTS.md, and the threats-to-validity
section discloses that the extended list was written after the first results had been seen.
