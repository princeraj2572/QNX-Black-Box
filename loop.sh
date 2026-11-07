#!/usr/bin/env bash
# Runs Claude Code one feature at a time. Every feature = exactly one commit, authored as you.
# Usage: GH_EMAIL=you@example.com ./loop.sh      (run in Git Bash, WSL, macOS or Linux)
set -euo pipefail
cd "$(dirname "$0")"

GH_USER="${GH_USER:-princeraj2572}"
GH_EMAIL="${GH_EMAIL:-}"            # must be an email linked to your GitHub account
MAX_ITERS="${MAX_ITERS:-30}"
MAX_TURNS="${MAX_TURNS:-40}"

if [ -z "$GH_EMAIL" ]; then
  echo "Set GH_EMAIL to the email linked to your GitHub account, e.g.:"
  echo "  GH_EMAIL=you@example.com ./loop.sh"
  exit 1
fi

# Force every commit (including ones made by the claude subprocess) to use your identity.
export GIT_AUTHOR_NAME="$GH_USER" GIT_AUTHOR_EMAIL="$GH_EMAIL"
export GIT_COMMITTER_NAME="$GH_USER" GIT_COMMITTER_EMAIL="$GH_EMAIL"

[ -d .git ] || git init -q -b main
git config user.name "$GH_USER"
git config user.email "$GH_EMAIL"
git config core.hooksPath .githooks
chmod +x .githooks/commit-msg
mkdir -p .loop

if ! git rev-parse HEAD >/dev/null 2>&1; then
  git add -A
  git commit -q -m "chore: add project plan and working rules"
fi

next_item() {
  grep -E '^- \[ \] ' PLAN.md | grep -v '\[HUMAN\]' | head -1
}

for i in $(seq 1 "$MAX_ITERS"); do
  item="$(next_item || true)"
  if [ -z "$item" ]; then
    echo "No automatable items left. Remaining [HUMAN] steps:"
    grep -E '^- \[ \].*\[HUMAN\]' PLAN.md || true
    exit 0
  fi
  echo "== Iteration $i: $item"

  before="$(git rev-parse HEAD)"
  rm -f .loop/blocked.md

  claude -p "$(cat .claude/loop-prompt.md)" \
    --permission-mode acceptEdits \
    --max-turns "$MAX_TURNS" 2>&1 | tee ".loop/iter-$i.log" || true

  if [ -f .loop/blocked.md ]; then
    echo "Claude reported a blocker:"; cat .loop/blocked.md; exit 2
  fi

  after="$(git rev-parse HEAD)"
  [ "$before" != "$after" ] || { echo "No commit was made. Stopping."; exit 3; }
  [ "$(git rev-list --count "$before..$after")" -eq 1 ] || { echo "More than one commit in one iteration. Stopping."; exit 4; }
  [ -z "$(git status --porcelain)" ] || { echo "Uncommitted changes left over. Stopping."; exit 5; }

  author="$(git log -1 --format='%an <%ae>')"
  [ "$author" = "$GH_USER <$GH_EMAIL>" ] || { echo "Unexpected author: $author. Stopping."; exit 6; }

  if git log -1 --format=%B | grep -qiE 'claude|anthropic|co-authored-by|generated with'; then
    echo "Commit message contains attribution. Stopping."; exit 7
  fi

  if [ -d tests ]; then
    python3 -m unittest discover -s tests -q || { echo "Tests fail after commit. Stopping."; exit 8; }
  fi

  git log -1 --format='   committed: %h %s'
done

echo "Reached MAX_ITERS=$MAX_ITERS. Run again to continue."
