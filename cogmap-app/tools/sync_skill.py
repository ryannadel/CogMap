#!/usr/bin/env python3
"""Sync the canonical CogMap skill to the Codex discovery path.

Canonical skill:  cogmap-app/skills/build-cogmap/
Codex copy:       .agents/skills/build-cogmap/   (scanned by OpenAI Codex CLI)

The skill is self-contained (SKILL.md + scripts/ + assets/ + requirements.txt), so
the copy is a full mirror of the canonical directory. Claude Code and Copilot CLI
read the canonical copy directly (via the plugin / ~/.copilot/skills); only Codex
needs the repo-root `.agents/skills` mirror.

Usage:
    python cogmap-app/tools/sync_skill.py            # regenerate the .agents copy
    python cogmap-app/tools/sync_skill.py --check    # exit 1 if the copy has drifted
"""
import filecmp
import shutil
import sys
import time
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]          # Project Osler / repo root
CANONICAL = REPO / "cogmap-app" / "skills" / "build-cogmap"
MIRROR = REPO / ".agents" / "skills" / "build-cogmap"

# Never mirror caches / regenerable cruft.
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".cogmap_initialized")


def _rel(p: pathlib.Path) -> str:
    return str(p.relative_to(REPO))


def _diff(a: pathlib.Path, b: pathlib.Path) -> list[str]:
    """Return a list of human-readable differences between dirs a and b."""
    out = []
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])

    def walk(c: filecmp.dircmp, base_a: pathlib.Path, base_b: pathlib.Path):
        for name in c.left_only:
            if name in ("__pycache__",) or name.endswith(".pyc"):
                continue
            out.append(f"missing in mirror: {_rel(base_a / name)}")
        for name in c.right_only:
            if name in ("__pycache__",) or name.endswith(".pyc"):
                continue
            out.append(f"extra in mirror:   {_rel(base_b / name)}")
        for name in c.diff_files:
            out.append(f"content differs:   {_rel(base_a / name)}")
        for name, sub in c.subdirs.items():
            walk(sub, base_a / name, base_b / name)

    walk(cmp, a, b)
    return out


def check() -> int:
    if not MIRROR.exists():
        print(f"MIRROR MISSING: {_rel(MIRROR)} (run without --check to create it)")
        return 1
    diffs = _diff(CANONICAL, MIRROR)
    if diffs:
        print("Skill copies have drifted:")
        for d in diffs:
            print("  " + d)
        print("Run: python cogmap-app/tools/sync_skill.py")
        return 1
    print(f"OK: {_rel(MIRROR)} matches {_rel(CANONICAL)}")
    return 0


def _safe_rmtree(p: pathlib.Path):
    """Robust against transient Windows/OneDrive/AV locks on the directory."""
    for _ in range(6):
        try:
            shutil.rmtree(p)
            return
        except FileNotFoundError:
            return
        except (PermissionError, OSError):
            time.sleep(0.5)
    for f in sorted(p.rglob("*"), reverse=True):
        try:
            f.unlink()
        except Exception:
            try:
                f.rmdir()
            except Exception:
                pass
    try:
        p.rmdir()
    except Exception:
        pass


def sync() -> int:
    if not CANONICAL.exists():
        print(f"canonical skill not found: {_rel(CANONICAL)}")
        return 1
    if MIRROR.exists():
        _safe_rmtree(MIRROR)
    MIRROR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CANONICAL, MIRROR, ignore=IGNORE, dirs_exist_ok=True)
    print(f"synced {_rel(CANONICAL)} -> {_rel(MIRROR)}")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv[1:] else sync())
