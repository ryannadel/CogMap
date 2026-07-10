import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "cogmap-app" / "skills" / "build-cogmap"
SCRIPTS_DIR = SKILL_DIR / "scripts"


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


if __name__ == "__main__":
    unittest.main()
