You are working in the QNX Black Box repo. Follow CLAUDE.md exactly.

1. Read CLAUDE.md and PLAN.md.
2. Take the first unchecked item that is not marked [HUMAN]. Do only that item.
3. Implement it with tests. Run `python3 -m unittest discover -s tests` and fix until it passes.
4. Tick the item's checkbox in PLAN.md.
5. Make exactly one commit: `git add -A && git commit -m "<type>: <summary>"`.
6. Stop. Do not start the next item.

If you cannot finish, write the reason to .loop/blocked.md and stop without committing.
