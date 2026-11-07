# QNX Black Box

Host-side tooling that records a QNX 8.0 system trace, injects faults, and explains in plain English why a real-time deadline was missed.

## Rules (non-negotiable)

- One feature per iteration. Take the first unchecked, non-[HUMAN] item in PLAN.md. Do nothing else.
- Implement it with tests. Run `python3 -m unittest discover -s tests` and only commit when it passes.
- Exactly one commit per feature: `git add -A && git commit -m "<type>: <summary>"`.
  - Types: feat, test, docs, chore, fix. Subject is imperative and at most 72 characters. A short body is optional.
- Tick the item's checkbox in PLAN.md in the same commit as the feature.
- Commit messages, code, comments and docs carry no tool or assistant attribution. No Co-Authored-By or other trailers.
- Never change git config, never use --author, never push, never amend or rewrite history, never use --no-verify.
- Python 3 standard library only. No new dependencies.
- Do not invent QNX facts. If a QNX behaviour or file format is unknown, code against the internal format in docs/trace-format.md, leave a `TODO(human)` comment, and move on.
- If you are blocked, write the reason to `.loop/blocked.md` and stop without committing.

## Layout

- `blackbox/` the Python package (parser, detectors, explainer, CLI, chaos, recorder, report)
- `tests/` unit tests and fixtures
- `docs/` trace format, report format, codelab
- `target/` C demo services for the QNX target (built by a human with qcc)
