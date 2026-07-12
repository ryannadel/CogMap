#!/usr/bin/env python3
"""Publish a built CogMap visualization to a GitHub Pages branch."""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


DEFAULT_BRANCH = "gh-pages"


def run(cmd, cwd=None, check=True):
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise RuntimeError("{} failed{}".format(" ".join(cmd), f":\n{detail}" if detail else ""))
    return result


def parse_github_remote(url):
    """Return (owner, repo) for common GitHub HTTPS/SSH remote URL forms."""
    patterns = (
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.match(pattern, url.strip())
        if match:
            return match.group("owner"), match.group("repo")
    return None, None


def pages_url(owner, repo, site_path="."):
    if not owner or not repo:
        return None
    base = f"https://{owner}.github.io/" if repo.lower() == f"{owner.lower()}.github.io" else f"https://{owner}.github.io/{repo}/"
    clean = site_path.strip().strip("/").strip(".")
    return base if not clean else base + clean + "/"


def copy_payload(output_dir, target_dir):
    output_dir = pathlib.Path(output_dir)
    target_dir = pathlib.Path(target_dir)
    html = output_dir / "knowledge-base-viz.html"
    data = output_dir / "knowledge-base-viz-data.json"
    if not html.exists():
        raise FileNotFoundError(f"missing built visualization: {html}")

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html, target_dir / "index.html")
    if data.exists():
        shutil.copy2(data, target_dir / data.name)

    (target_dir / ".nojekyll").write_text("", encoding="utf-8")
    manifest = {
        "name": "CogMap",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "entrypoint": "index.html",
        "source_html": html.name,
        "data_file": data.name if data.exists() else None,
    }
    (target_dir / "cogmap-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def ensure_git_identity(worktree):
    name = run(["git", "config", "user.name"], cwd=worktree, check=False).stdout.strip()
    email = run(["git", "config", "user.email"], cwd=worktree, check=False).stdout.strip()
    if not name:
        run(["git", "config", "user.name", "CogMap Publisher"], cwd=worktree)
    if not email:
        run(["git", "config", "user.email", "cogmap-publisher@users.noreply.github.com"], cwd=worktree)


def ref_exists(repo_root, ref):
    return run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo_root, check=False).returncode == 0


def add_pages_worktree(repo_root, worktree, remote, branch):
    run(["git", "fetch", remote, branch, "--depth=1"], cwd=repo_root, check=False)
    remote_ref = f"refs/remotes/{remote}/{branch}"
    local_ref = f"refs/heads/{branch}"
    if ref_exists(repo_root, remote_ref):
        run(["git", "worktree", "add", "-B", branch, str(worktree), f"{remote}/{branch}"], cwd=repo_root)
        return
    if ref_exists(repo_root, local_ref):
        run(["git", "worktree", "add", str(worktree), branch], cwd=repo_root)
        return

    run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"], cwd=repo_root)
    run(["git", "checkout", "--orphan", branch], cwd=worktree)
    run(["git", "rm", "-rf", "."], cwd=worktree, check=False)
    for child in worktree.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def enable_pages(owner, repo, branch):
    if not owner or not repo:
        return "Skipped Pages enablement: remote is not a github.com repository."
    if shutil.which("gh") is None:
        return "Skipped Pages enablement: GitHub CLI (`gh`) is not installed."

    endpoint = f"repos/{owner}/{repo}/pages"
    get_result = run(["gh", "api", endpoint], check=False)
    verb = "PUT" if get_result.returncode == 0 else "POST"
    result = run(
        [
            "gh",
            "api",
            "-X",
            verb,
            endpoint,
            "-f",
            f"source[branch]={branch}",
            "-f",
            "source[path]=/",
        ],
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        return "Pages branch was pushed, but automatic Pages enablement failed: {}".format(detail or "unknown error")
    return "GitHub Pages is configured to serve from {}/.".format(branch)


def publish(args):
    repo_root = pathlib.Path(args.repo_root or ".").resolve()
    if not (repo_root / ".git").exists():
        repo_root = pathlib.Path(run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root).stdout.strip())

    remote_url = run(["git", "remote", "get-url", args.remote], cwd=repo_root, check=False).stdout.strip()
    owner, repo = parse_github_remote(remote_url) if remote_url else (None, None)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cogmap-pages-"))
    worktree = tmp / "worktree"
    committed = False
    try:
        add_pages_worktree(repo_root, worktree, args.remote, args.branch)
        target = worktree if args.site_path in ("", ".", "/") else worktree / args.site_path.strip("/\\")
        copy_payload(args.output, target)
        run(["git", "add", "-A"], cwd=worktree)
        if run(["git", "diff", "--cached", "--quiet"], cwd=worktree, check=False).returncode == 0:
            print("GitHub Pages branch already matches the current CogMap output.")
        else:
            ensure_git_identity(worktree)
            run(["git", "commit", "-m", "Publish CogMap visualization"], cwd=worktree)
            committed = True
            print("Committed CogMap output to {}.".format(args.branch))

        if args.no_push:
            print("Published locally to branch {} (--no-push).".format(args.branch))
        else:
            if not remote_url:
                raise RuntimeError(f"remote `{args.remote}` was not found")
            run(["git", "push", args.remote, args.branch], cwd=worktree)
            print("Pushed CogMap output to {}/{}.".format(args.remote, args.branch))
            if not args.no_enable_pages:
                print(enable_pages(owner, repo, args.branch))

        url = pages_url(owner, repo, args.site_path)
        if url:
            print("CogMap Pages URL: {}".format(url))
        elif args.no_push:
            print("No Pages URL available until the branch is pushed to a github.com remote.")
        return committed
    finally:
        run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Directory containing knowledge-base-viz.html.")
    parser.add_argument("--repo-root", default=".", help="Git repository to publish from.")
    parser.add_argument("--remote", default="origin", help="Git remote to push to.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Pages branch to create/update.")
    parser.add_argument("--site-path", default=".", help="Optional subdirectory within the Pages branch.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally but do not push.")
    parser.add_argument("--no-enable-pages", action="store_true", help="Do not configure Pages with gh.")
    return parser.parse_args(argv)


def main(argv=None):
    try:
        publish(parse_args(argv or sys.argv[1:]))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
