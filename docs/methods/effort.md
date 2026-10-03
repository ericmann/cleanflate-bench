# Effort, cost and provenance methods (SPEC 3.9)

## Round windows

"Round" means a cleanflate release round (one Foundry flight per tag in `config/rounds.json`), not a
review round. Windows follow committer time in the pinned clone: round 1 runs from the first commit to
the r1 tag commit inclusive, and round N from the r(N-1) tag commit (exclusive) to the rN tag commit.

## Stage wall-clock (`cfbench.effort.history`)

Each commit's gap since the previous commit (committer-time order over the whole history) is attributed
to that commit's `[stage:<s>] [task:<t>]` tag; commits without a tag count as `untagged`. This is an
estimate: a commit lands when work finishes, so the gap measures the work that produced it, but the
first commit of a stage inherits any idle time before it. Gaps longer than `effort.idle_gap_hours` (3 h)
are treated as idle (overnight pauses, waiting on review or a human) and reported separately as
`idle_seconds`, so wall-clock per round is `attributed_seconds + idle_seconds`. Milestones come from the
task-id phase prefix (`P0`..`P5`), `R<n>` for review-fix tasks, `other` for the rest.

## Models, review rounds, denials

- Models per stage come from the tool log (`provenance/tool-log.snapshot.jsonl` at the last round, which
  is cumulative): the count of tool calls per `(foundry_stage, model)`. Entries from before the Foundry
  stage was recorded appear under `unknown`. This counts tool calls, not tokens.
- Review rounds come from `.foundry/state.json` at each round's tag (`rounds[]` with verdicts).
- Denied calls are grouped by the prefix map in `config/bench.toml` (`effort.denial_categories`, first
  match wins; unmatched reasons are `other`).

## Forbidden-read audit

The guard only records what it refused. The audit asks the converse question: did any *allowed* call
touch prior art anyway? It reads the same tool-log snapshot and, for every allowed call by a
read-capable tool (`effort.forbidden_reads.read_tools`), extracts path-like tokens: the whole target for
file tools, and for `Bash` every word that starts with `/` or `~` after splitting on shell separators
(so a path inside a pipeline or an inline script is still seen). A token is a candidate when it matches
one of `effort.forbidden_reads.root_patterns` (cargo registry and git checkouts, build-script output,
rustdoc sources, system and Homebrew include trees) or names a prior-art word
(`effort.forbidden_reads.words`, which mirrors the guard's `FORBIDDEN_WORDS`) outside the build
checkout (`repo_root`).

The rule over-reports by design: a regex or a message that merely names a path is a candidate. Each
candidate is classified by hand in `config/forbidden_read_verdicts.toml` as `not-a-read` or `read`, keyed
by its timestamp. A candidate with no verdict counts as a forbidden read. `effort_totals` carries
`read_calls`, `forbidden_read_candidates` and `forbidden_reads` per round, and `effort_forbidden_reads`
lists every candidate with its verdict.

The log records top-level tool calls only. Subprocesses of make targets and interpreter escapes are not
logged individually (cleanflate's `provenance/README.md` lists these gaps), so the audit bounds what was
read; it does not prove that nothing else was.

## Defects

`Defects-caught:` trailers (other than `none`) are mapped to a source by keyword
(`effort.defect_keywords`): fuzzing, conformance, unit tests, review, else `other`. When several
sources match, the stage breaks the tie, and a commit with no keyword match in a `review` or `fix`
stage counts as review.

## Human interventions

Parsed from the tables in `provenance/human-interventions.md`: count per round, the `what` text and the
timestamp. A `phase-N` mention in the stage/task column assigns the round; otherwise the timestamp
does (date-only entries count as 00:00Z, so their round is approximate). Durations are not recorded in
that file, so time spent by humans is a documented gap and is not estimated here.
