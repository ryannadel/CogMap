# Contributing to CogMap

Thanks for helping improve CogMap. The project is a self-contained coding-agent
skill plus a deterministic Python pipeline, so most changes should keep the
agent instructions, Python scripts, demo assets, and mirrored skill copy aligned.

## Development setup

Requirements:

- Python 3.10 or newer
- No required third-party packages for Markdown/text notes
- `olefile` only if you are testing `.onex` conversion:

```bash
python -m pip install -r cogmap-app/requirements.txt
```

## Validation before opening a pull request

Run these checks from the repository root:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python cogmap-app/tools/sync_skill.py --check
```

If `sync_skill.py --check` reports drift, regenerate the Codex mirror:

```bash
python cogmap-app/tools/sync_skill.py
```

Then rerun the checks.

## Skill source of truth

The canonical skill lives at:

```text
cogmap-app/skills/build-cogmap/
```

The OpenAI Codex discovery copy lives at:

```text
.agents/skills/build-cogmap/
```

Do not edit the `.agents` copy directly. Edit the canonical skill, run
`python cogmap-app/tools/sync_skill.py`, and commit both the canonical change and
the regenerated mirror.

## Pull request guidance

- Keep changes focused and small enough to review.
- Add or update tests for behavior changes.
- Preserve the runtime separation between the immutable skill engine and the
  user workspace (`./cogmap` by default).
- Do not commit personal notes, generated workspaces, `.onex` exports, or
  generated `knowledge-base-viz.html` files outside the bundled synthetic demo.
- Prefer clear failure messages over silent fallbacks when user action is needed.

## Demo refresh

The bundled synthetic demo should render from a fresh workspace with:

```bash
COGMAP_NO_OPEN=1 python cogmap-app/skills/build-cogmap/scripts/refresh.py --no-open
```

The automated test suite runs this path in a temporary workspace.
