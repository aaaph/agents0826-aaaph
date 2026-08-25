---
description: Check the team Claude Code setup — vector DB access, embedding model, project skills
---

Run the setup verification script and show the result to the user:

```bash
bash "$(git rev-parse --show-toplevel 2>/dev/null || pwd)/deploy/verify_setup.sh"
```

If any line is `FAIL`, explain it briefly and point at `README.md` / `docs/ONBOARDING.md`.
If everything is `OK`, confirm the setup is ready to use.
