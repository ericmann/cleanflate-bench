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
