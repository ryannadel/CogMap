import json
import os
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "cogmap-app" / "skills" / "build-cogmap"
SCRIPTS_DIR = SKILL_DIR / "scripts"

_publish_spec = importlib.util.spec_from_file_location(
    "publish_github_pages", SCRIPTS_DIR / "publish_github_pages.py"
)
publish_github_pages = importlib.util.module_from_spec(_publish_spec)
_publish_spec.loader.exec_module(publish_github_pages)


def run_script(script, workspace, cwd=None, *args):
    env = dict(os.environ)
    if workspace is not None:
        env["COGMAP_APP"] = str(workspace)
    env["COGMAP_NO_OPEN"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class CogMapPipelineTests(unittest.TestCase):
    def test_date_parsing_preserves_valid_month_days(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "cogmap"
            sources = workspace / "sources"
            sources.mkdir(parents=True)
            (sources / "dated-notes.txt").write_text(
                "On January 31, 2025 the team made a concrete decision about "
                "the platform roadmap and recorded several follow-up questions. "
                "On 2025-12-31 there was another substantial roadmap update. "
                "The February 29, 2024 leap-day note remains valid. "
                "April 31, 2025 is intentionally invalid and should be ignored.",
                encoding="utf-8",
            )

            result = run_script("v3_prep.py", workspace)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            master = json.loads((workspace / "work" / "v3_chunks_master.json").read_text(encoding="utf-8"))
            self.assertEqual(len(master["chunks"]), 1)
            dates = set(master["chunks"][0]["dates"])
            self.assertIn("2025-01-31", dates)
            self.assertIn("2025-12-31", dates)
            self.assertIn("2024-02-29", dates)
            self.assertNotIn("2025-01-28", dates)
            self.assertNotIn("2025-12-28", dates)
            self.assertNotIn("2025-04-30", dates)
            self.assertNotIn("2025-04-31", dates)

    def test_demo_refresh_renders_html(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "cogmap"

            result = run_script("refresh.py", None, Path(td), "--no-open")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("DONE.", result.stdout)
            html = workspace / "output" / "knowledge-base-viz.html"
            data_path = workspace / "output" / "knowledge-base-viz-data.json"
            self.assertTrue(html.exists(), result.stdout)
            self.assertTrue(data_path.exists(), result.stdout)
            data = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertGreater(data["metadata"]["counts"]["sources"], 0)
            self.assertGreater(data["metadata"]["counts"]["chunks"], 0)
            self.assertIn("CogMap", html.read_text(encoding="utf-8"))

    def test_publish_remote_parsing_and_url(self):
        cases = [
            ("https://github.com/octo/demo.git", ("octo", "demo")),
            ("git@github.com:octo/demo.git", ("octo", "demo")),
            ("ssh://git@github.com/octo/demo.git", ("octo", "demo")),
        ]
        for remote, expected in cases:
            with self.subTest(remote=remote):
                self.assertEqual(publish_github_pages.parse_github_remote(remote), expected)
        self.assertEqual(publish_github_pages.pages_url("octo", "demo"), "https://octo.github.io/demo/")
        self.assertEqual(publish_github_pages.pages_url("octo", "octo.github.io"), "https://octo.github.io/")

    def test_publish_github_pages_no_push_creates_branch_payload(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            output = repo / "cogmap" / "output"
            output.mkdir(parents=True)
            (output / "knowledge-base-viz.html").write_text("<html>CogMap</html>", encoding="utf-8")
            (output / "knowledge-base-viz-data.json").write_text('{"metadata": {}}', encoding="utf-8")

            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            (repo / "README.md").write_text("test\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "publish_github_pages.py"),
                    "--repo-root",
                    str(repo),
                    "--output",
                    str(output),
                    "--no-push",
                    "--no-enable-pages",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Published locally to branch gh-pages", result.stdout)
            html = subprocess.run(
                ["git", "show", "gh-pages:index.html"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
            self.assertEqual(html, "<html>CogMap</html>")


if __name__ == "__main__":
    unittest.main()
