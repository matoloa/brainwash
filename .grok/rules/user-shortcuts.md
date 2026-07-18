# User chat shortcuts (persistent)

Bare single-letter messages mean:

| Shortcut | Action |
|----------|--------|
| **`p`** | Commit and push (stage, commit with a good message, push to tracking branch). Not “open a PR” unless asked. |
| **`n`** | Proceed with the **next phase of the active plan** (implement it; do not re-confirm the phase). |

If both a plan and unrelated dirty files exist, `p` commits the intentional work; ask only if the dirty set looks mixed or risky (force-push, protected branch, secrets).
