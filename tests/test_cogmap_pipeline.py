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

_extraction_spec = importlib.util.spec_from_file_location(
    "extraction_batches", SCRIPTS_DIR / "extraction_batches.py"
)
extraction_batches = importlib.util.module_from_spec(_extraction_spec)
_extraction_spec.loader.exec_module(extraction_batches)


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
    def test_adaptive_batching_targets_nine_bounded_batches(self):
        items = [
            {"chunk_id": f"chunk_{index}", "text": "x" * 1000}
            for index in range(1761)
        ]

        batches, guidance = extraction_batches.batch_items(items)

        self.assertGreaterEqual(len(batches), 8)
        self.assertLessEqual(len(batches), 10)
        self.assertEqual(guidance["target_batch_count"], 9)
        self.assertGreaterEqual(
            guidance["selected_batch_chars"], extraction_batches.MIN_BATCH_CHARS
        )
        self.assertLessEqual(
            guidance["selected_batch_chars"], extraction_batches.MAX_BATCH_CHARS
        )
        self.assertTrue(
            all(
                len(batch) <= extraction_batches.MAX_BATCH_CHUNKS
                for batch in batches
            )
        )

    def test_extraction_validation_rejects_encoding_schema_and_provenance_errors(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "extract.json"
            output.write_bytes(b"\xff")
            _, errors = extraction_batches.load_extraction_output(
                output, {"chunk_allowed"}
            )
            self.assertIn("not valid UTF-8", errors[0])

            output.write_text("{", encoding="utf-8")
            _, errors = extraction_batches.load_extraction_output(
                output, {"chunk_allowed"}
            )
            self.assertIn("not valid JSON", errors[0])

            output.write_text(
                json.dumps(
                    {
                        "concepts": [
                            {
                                "name": "Known",
                                "type": "InvalidType",
                                "definition": "Definition",
                                "aliases": [],
                                "chunk_ids": ["chunk_foreign"],
                            }
                        ],
                        "claims": [
                            {
                                "text": "Claim",
                                "status": "InvalidStatus",
                                "concepts": ["Missing"],
                                "chunk_id": "chunk_foreign",
                                "date": None,
                            }
                        ],
                        "relations": [
                            {
                                "source": "Known",
                                "target": "Missing",
                                "type": "invalid_relation",
                                "evidence_chunk_ids": ["chunk_foreign"],
                                "rationale": "Rationale",
                            }
                        ],
                        "extra": [],
                    }
                ),
                encoding="utf-8",
            )
            _, errors = extraction_batches.load_extraction_output(
                output, {"chunk_allowed"}
            )
            diagnostics = "\n".join(errors)
            self.assertIn("top-level: unexpected fields: extra", diagnostics)
            self.assertIn("concepts[0].type", diagnostics)
            self.assertIn("concepts[0].chunk_ids: IDs outside this batch", diagnostics)
            self.assertIn("claims[0].status", diagnostics)
            self.assertIn("claims[0].concepts: unknown concept references", diagnostics)
            self.assertIn("relations[0].target: unknown concept reference", diagnostics)
            self.assertIn(
                "relations[0].evidence_chunk_ids: IDs outside this batch",
                diagnostics,
            )

            provenance_errors = extraction_batches.validate_extraction_data(
                {
                    "concepts": [
                        {
                            "name": "Known",
                            "type": "Concept",
                            "definition": "Definition",
                            "aliases": [],
                            "chunk_ids": [],
                        }
                    ],
                    "claims": [],
                    "relations": [
                        {
                            "source": "Known",
                            "target": "Known",
                            "type": "relates_to",
                            "evidence_chunk_ids": [],
                            "rationale": "Rationale",
                        }
                    ],
                },
                {"chunk_allowed"},
            )
            self.assertTrue(
                any(
                    "expected at least one batch chunk ID" in error
                    for error in provenance_errors
                )
            )

    def test_extraction_partial_resume_and_idempotent_ingestion(self):
        valid_output = {"concepts": [], "claims": [], "relations": []}
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "cogmap"
            sources = workspace / "sources"
            sources.mkdir(parents=True)
            lines = [
                (
                    f"Entry {index} describes a durable knowledge graph extraction "
                    + "workflow with grounded evidence and reliable resumability. " * 7
                )
                for index in range(120)
            ]
            (sources / "large-notes.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )

            first = run_script("refresh.py", workspace, None, "--no-open")

            self.assertEqual(first.returncode, 10, first.stdout + first.stderr)
            cache = workspace / "work" / "refresh_cache"
            delta = workspace / "work" / "refresh_delta"
            action = json.loads((cache / "action.json").read_text(encoding="utf-8"))
            manifest_path = Path(action["manifest"])
            manifest_text = manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(manifest_text)
            self.assertGreaterEqual(action["progress"]["total"], 3)
            self.assertEqual(action["orchestration"]["strategy"], "bounded_parallel")
            self.assertLessEqual(
                action["orchestration"]["max_concurrency"],
                extraction_batches.MAX_EXTRACTION_CONCURRENCY,
            )

            first_batch = manifest["batches"][0]
            first_payload = json.dumps(valid_output)
            Path(first_batch["output"]).write_text(first_payload, encoding="utf-8")
            invalid_batch = manifest["batches"][1]
            Path(invalid_batch["output"]).write_text(
                '{"concepts": [], "claims": []}', encoding="utf-8"
            )

            resumed = run_script("refresh.py", workspace, None, "--no-open")

            self.assertEqual(resumed.returncode, 10, resumed.stdout + resumed.stderr)
            resumed_action = json.loads(
                (cache / "action.json").read_text(encoding="utf-8")
            )
            self.assertEqual(resumed_action["progress"]["valid"], 1)
            self.assertEqual(
                resumed_action["progress"]["pending"],
                resumed_action["progress"]["total"] - 1,
            )
            self.assertIn(
                first_batch["batch_id"], resumed_action["completed_batch_ids"]
            )
            self.assertNotIn(
                first_batch["batch_id"],
                {batch["batch_id"] for batch in resumed_action["batches"]},
            )
            invalid = next(
                batch
                for batch in resumed_action["batches"]
                if batch["batch_id"] == invalid_batch["batch_id"]
            )
            self.assertEqual(invalid["status"], "invalid")
            self.assertTrue(
                any("missing fields: relations" in error for error in invalid["diagnostics"])
            )
            self.assertEqual(
                Path(first_batch["output"]).read_text(encoding="utf-8"),
                first_payload,
            )

            for batch in resumed_action["batches"]:
                Path(batch["output"]).write_text(
                    json.dumps(valid_output), encoding="utf-8"
                )
            saved_outputs = {
                batch["output"]: Path(batch["output"]).read_text(encoding="utf-8")
                for batch in manifest["batches"]
            }
            legacy_manifest = json.loads(manifest_text)
            for batch in legacy_manifest["batches"]:
                batch.pop("batch_id")
            manifest_path.write_text(
                json.dumps(legacy_manifest), encoding="utf-8"
            )
            extraction_dir = workspace / "work" / "v3_extract"
            extraction_dir.mkdir(exist_ok=True)
            legacy_archive = extraction_dir / "extract_delta_1700000000_00.json"
            legacy_archive.write_text(first_payload, encoding="utf-8")

            completed = run_script("refresh.py", workspace, None, "--no-open")

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            archives = sorted(extraction_dir.glob("extract_delta_*.json"))
            self.assertEqual(len(archives), len(manifest["batches"]))
            self.assertFalse(legacy_archive.exists())
            self.assertEqual(
                {path.stem.removeprefix("extract_delta_") for path in archives},
                {batch["batch_id"] for batch in manifest["batches"]},
            )

            delta.mkdir()
            (delta / "manifest.json").write_text(manifest_text, encoding="utf-8")
            for path, payload in saved_outputs.items():
                Path(path).write_text(payload, encoding="utf-8")

            repeated = run_script("refresh.py", workspace, None, "--no-open")

            self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            self.assertEqual(
                len(list(extraction_dir.glob("extract_delta_*.json"))),
                len(manifest["batches"]),
            )

    def test_synthesis_cannot_run_ahead_of_stale_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "cogmap"
            sources = workspace / "sources"
            sources.mkdir(parents=True)
            (sources / "notes.txt").write_text(
                "A grounded concept needs resolution before synthesis can proceed.",
                encoding="utf-8",
            )
            first = run_script("refresh.py", workspace, None, "--no-open")
            self.assertEqual(first.returncode, 10, first.stdout + first.stderr)
            action_path = workspace / "work" / "refresh_cache" / "action.json"
            action = json.loads(action_path.read_text(encoding="utf-8"))
            batch = action["batches"][0]
            Path(batch["output"]).write_text(
                json.dumps(
                    {
                        "concepts": [
                            {
                                "name": "Grounded Concept",
                                "type": "Concept",
                                "definition": "A concept grounded in the source.",
                                "aliases": [],
                                "chunk_ids": [batch["chunk_ids"][0]],
                            }
                        ],
                        "claims": [],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            blocked = run_script(
                "refresh.py", workspace, None, "--no-open", "--with-synth"
            )

            self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
            self.assertIn(
                "synthesis is blocked until stale resolution is handled",
                blocked.stdout,
            )

    def test_oversized_source_chunk_is_split_before_batching(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td) / "cogmap"
            sources = workspace / "sources"
            sources.mkdir(parents=True)
            oversized = "word " * (
                extraction_batches.MAX_BATCH_CHARS // len("word ") + 10
            )
            (sources / "oversized.md").write_text(
                f"# Oversized\n\n{oversized}", encoding="utf-8"
            )

            result = run_script("v3_prep.py", workspace)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            master = json.loads(
                (workspace / "work" / "v3_chunks_master.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(master["chunks"]), 2)
            self.assertTrue(
                all(
                    len(chunk["text"]) <= extraction_batches.MAX_BATCH_CHARS
                    for chunk in master["chunks"]
                )
            )

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
            html_text = html.read_text(encoding="utf-8")
            self.assertIn("CogMap", html_text)
            self.assertIn("Knowledge review inbox", html_text)
            self.assertIn("data-view=\"review\"", html_text)
            self.assertIn("localStorage.setItem(reviewStorageKey()", html_text)
            self.assertIn("window.location.pathname", html_text)
            self.assertIn("Review evidence", html_text)

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
