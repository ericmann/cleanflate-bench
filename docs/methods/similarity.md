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
