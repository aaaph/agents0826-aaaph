#!/usr/bin/env python3
"""Cross-platform onboarding for the team Claude Code setup (Windows / macOS / Linux).

Run once after cloning this repo:

    python deploy/bootstrap.py          (Windows: py deploy\\bootstrap.py
                                         or double-click deploy\\bootstrap.cmd)

Does:
  1. Create memory-hooks venv + install deps (incl. the embedding model extra) via uv.
  2. Pre-download the embedding model (~120 MB for the default e5-small).
  3. Merge the team baseline (hooks + plugins) into ~/.claude/settings.json with the
     correct platform-specific python path, and set HOOKS_NEO4J_* env.
  4. Verify connectivity to the shared Neo4j.

Password sources, in order: NEO4J_PASSWORD env → hidden prompt → visible prompt.
(getpass is unreliable under Git Bash/MINGW on Windows: it can return '' without
waiting, which would silently store an empty password.)
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "memory-hooks"
BASELINE = ROOT / "shared" / ".claude" / "settings.json"
SETTINGS = Path.home() / ".claude" / "settings.json"

# Set NEO4J_HOST (or full HOOKS_NEO4J_URI) for your company before rollout.
DEFAULT_URI = os.environ.get(
    "HOOKS_NEO4J_URI",
    f"bolt://{os.environ.get('NEO4J_HOST', '<NEO4J_HOST>')}:7687",
)

IS_WIN = platform.system() == "Windows"


def venv_python(venv: Path) -> Path:
    """Path to the python inside a venv, per-platform."""
    return venv / ("Scripts/python.exe" if IS_WIN else "bin/python")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"   $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def have(tool: str) -> bool:
    from shutil import which
    return which(tool) is not None


def prompt_password() -> str:
    """Read the shared Neo4j password robustly across platforms."""
    env = os.environ.get("NEO4J_PASSWORD", "").strip()
    if env:
        print("   (password taken from NEO4J_PASSWORD)")
        return env
    for _ in range(3):
        try:
            pw = getpass.getpass("   Shared Neo4j password (ask your team lead): ").strip()
        except Exception:
            pw = ""
        if pw:
            return pw
        print("   (hidden input unavailable — the password will be visible as you type)")
        try:
            pw = input("   Shared Neo4j password: ").strip()
        except EOFError:
            pw = ""
        if pw:
            return pw
        print("   Empty password, try again.")
    return ""


def main() -> int:
    print("== Claude Code team onboarding ==")
    if "<NEO4J_HOST>" in DEFAULT_URI:
        print("WARNING: NEO4J host is not configured yet.")
        print("  Set it once for your company, e.g.:")
        print("    export NEO4J_HOST=neo4j.example.internal      # macOS/Linux")
        print("    setx NEO4J_HOST neo4j.example.internal        # Windows")
        print("  or edit DEFAULT_URI in deploy/bootstrap.py.\n")

    if not have("uv"):
        print("ERROR: 'uv' not found. Install it:")
        print("  Windows : powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
        print("  mac/lin : curl -LsSf https://astral.sh/uv/install.sh | sh")
        return 1

    # 1. venv + deps
    print("==> 1/4 venv + dependencies")
    os.chdir(HOOKS)
    subprocess.run(["uv", "venv", "--python", "3.11"], check=False)
    run(["uv", "pip", "install", "-e", ".[embeddings]"])
    py = venv_python(HOOKS / ".venv")
    if not py.exists():
        print(f"ERROR: python not found in venv: {py}")
        return 1

    # 2. pre-download model
    model = os.environ.get("AGENT_MEMORY_EMBED_MODEL", "e5-small")
    print(f"==> 2/4 pre-downloading embedding model ({model})")
    run([str(py), "-c",
         "import os,sys;sys.path.insert(0,'hooks');"
         "from embed import _get_model;_get_model();print('   model cached')"])

    # 3. merge baseline into ~/.claude/settings.json
    print("==> 3/4 configuring ~/.claude/settings.json")
    pw = prompt_password()
    if not pw:
        print("ERROR: empty password — Neo4j settings not written.")
        print("Re-run, or pass it via: NEO4J_PASSWORD=... python deploy/bootstrap.py")
        return 1

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    cur = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw = json.dumps(base).replace("{{MEMORY_HOOKS}}", str(HOOKS).replace("\\", "/"))
    base = json.loads(raw)
    cur.setdefault("hooks", {}).update(base.get("hooks", {}))
    cur.setdefault("enabledPlugins", {}).update(base.get("enabledPlugins", {}))
    env = cur.setdefault("env", {})
    env["HOOKS_NEO4J_URI"] = DEFAULT_URI
    env["HOOKS_NEO4J_USER"] = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
    env["HOOKS_NEO4J_PASSWORD"] = pw
    SETTINGS.write_text(json.dumps(cur, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"   updated {SETTINGS}")

    # 4. verify
    print("==> 4/4 verifying connection to the shared Neo4j")
    env_run = {**os.environ, "HOOKS_NEO4J_URI": DEFAULT_URI,
               "HOOKS_NEO4J_USER": env["HOOKS_NEO4J_USER"], "HOOKS_NEO4J_PASSWORD": pw}
    r = subprocess.run([str(py), str(HOOKS / "hooks" / "query_memory_v2.py"),
                        "smoke test", "--limit", "1"],
                       env=env_run, capture_output=True, text=True)
    if r.returncode == 0 and "[" in (r.stdout or ""):
        print("   OK — connected to shared memory")
    else:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
        print("   WARNING — could not connect (VPN? password? host?).")
        if tail:
            print("   ", tail[0])

    print("\nDone. Restart Claude Code, then run /verify-setup in a session.")
    if IS_WIN:
        print("Windows: shell hooks run through Git Bash — make sure Git for Windows is installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
