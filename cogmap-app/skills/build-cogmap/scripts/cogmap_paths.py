"""Central path resolver for the self-contained CogMap skill.

The *engine* (these scripts) lives in the skill's `scripts/` folder. Runtime data
lives in a *workspace* the user controls, so an installed skill never writes the
user's notes or generated output into a shared/global skill directory.

Workspace root (APP) resolution order:
  1. `COGMAP_APP` env var, if set (advanced / explicit relocation).
  2. Legacy repo layout: if these scripts sit in a folder literally named
     `pipeline`, the app is its parent (backward compatible with the original
     `cogmap-app/` checkout that kept sources/work/output beside `pipeline/`).
  3. Otherwise a project-local `./cogmap` folder under the current working dir.

Individual folders can still be overridden with `COGMAP_SOURCES`, `COGMAP_WORK`,
`COGMAP_OUTPUT` (legacy `OSLER_*` names are accepted as fallbacks).

On first use of a project-local workspace, the pipeline seeds it from the bundled
demo (`<skill>/assets/demo/`) so a fresh install renders immediately. Once the
user drops their own notes into `sources/` and refreshes, the pipeline's
foreign-corpus reset takes over and clears the demo artifacts.
"""
import os
import pathlib
import shutil


def _env(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return pathlib.Path(v)
    return None


# Where these scripts live (the skill's scripts/ dir). refresh.py runs its
# sibling stage scripts from here; PIPELINE is kept as a backward-compatible alias.
SCRIPTS = pathlib.Path(__file__).resolve().parent
PIPELINE = SCRIPTS

# Bundled demo corpus + prebuilt artifacts (present only in the packaged skill).
_DEMO = SCRIPTS.parent / "assets" / "demo"


def _resolve_app():
    env = _env("COGMAP_APP", "OSLER_APP")
    if env:
        return env, False
    if SCRIPTS.name == "pipeline":
        # Legacy cogmap-app/ checkout: data lives beside pipeline/.
        return SCRIPTS.parent, False
    # Installed self-contained skill: keep the workspace out of the skill dir.
    return pathlib.Path.cwd() / "cogmap", True


APP, _project_local = _resolve_app()

# Pin the resolved app into the environment so child processes (refresh.py spawns
# the stage scripts with a different cwd) resolve to the SAME workspace instead of
# re-deriving a project-local path from their own cwd.
os.environ["COGMAP_APP"] = str(APP)

SOURCES = _env("COGMAP_SOURCES", "OSLER_SOURCES") or APP / "sources"
WORK = _env("COGMAP_WORK", "OSLER_WORK") or APP / "work"
OUTPUT = _env("COGMAP_OUTPUT", "OSLER_OUTPUT") or APP / "output"


def _seed_from_demo():
    """Copy the bundled demo into a brand-new project-local workspace once."""
    marker = APP / ".cogmap_initialized"
    if marker.exists() or not _DEMO.exists():
        return
    APP.mkdir(parents=True, exist_ok=True)
    for sub, dest in (("sources", SOURCES), ("work", WORK), ("output", OUTPUT)):
        src = _DEMO / sub
        if src.exists():
            shutil.copytree(src, dest, dirs_exist_ok=True)
    marker.write_text("seeded from bundled demo\n", encoding="utf-8")


if _project_local:
    _seed_from_demo()

for _d in (SOURCES, WORK, OUTPUT):
    _d.mkdir(parents=True, exist_ok=True)
