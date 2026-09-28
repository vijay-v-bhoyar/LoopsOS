"""Observable inventory invariants; run with python -B -m unittest discover."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from inventory_skills import inventory, main, parse_metadata


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def skill(self, relative: str, text: str = "---\nname: sample\ndescription: Sample skill.\n---\nBody.\n") -> Path:
        path = self.base / relative / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
        return path

    def test_identical_copies_match_and_content_drift_is_ambiguous(self):
        first = self.skill("personal/a")
        second = self.skill("plugin/b")
        roots = [("personal", str(first.parent.parent)), ("plugin", str(second.parent.parent))]
        same = inventory(roots, ["sample", "absent", "sample"])
        self.assertEqual(same["stats"]["files"], 2)
        self.assertEqual(same["duplicate_names"][0]["status"], "IDENTICAL")
        self.assertEqual([item["status"] for item in same["resolutions"]], ["MATCH", "MISSING"])
        self.assertEqual(len(same["resolutions"][0]["copies"]), 2)
        second.write_text(second.read_text(encoding="utf-8") + "Changed body.\n", encoding="utf-8")
        changed = inventory(roots, ["sample"])
        self.assertEqual(changed["duplicate_names"][0]["status"], "DRIFTED")
        self.assertEqual(changed["resolutions"][0]["status"], "AMBIGUOUS")
        self.assertEqual(len(changed["resolutions"][0]["copies"]), 2)

    def test_overlap_records_all_memberships_without_fake_duplicates(self):
        path = self.skill("root/nested/a")
        roots = [("personal", str(self.base / "root")),
                 ("repo", str(self.base / "root/nested")),
                 ("personal", str(self.base / "root"))]
        report = inventory(roots, ["sample"])
        self.assertEqual(report["stats"]["roots"], 2)
        self.assertEqual(report["stats"]["files"], 1)
        self.assertEqual(report["duplicate_names"], [])
        self.assertEqual(report["skills"][0]["path"], str(path))
        self.assertEqual(report["skills"][0]["categories"], ["personal", "repo"])
        self.assertEqual(len(report["skills"][0]["sources"]), 2)
        self.assertEqual(report["resolutions"][0]["status"], "MATCH")

    def test_missing_frontmatter_and_invalid_names_are_not_invented(self):
        self.skill("invented-name", "# no frontmatter\n")
        self.skill("invalid-name", "---\nname: [sample, other]\ndescription: Fine\n---\n")
        self.skill("unclosed-name", "---\nname: sample\ndescription: Fine\n")
        report = inventory([("personal", str(self.base))], ["invented-name", "sample"])
        self.assertTrue(all(skill["name"] is None for skill in report["skills"]))
        self.assertTrue(all(skill["metadata_errors"] for skill in report["skills"]))
        self.assertEqual(report["stats"]["metadata_errors"], 3)
        self.assertTrue(all(item["status"] == "MISSING" for item in report["resolutions"]))

    def test_bom_quotes_folded_description_and_byte_hash(self):
        content = '\ufeff---\nname: "plugin:sample" # comment\ndescription: >-\n  First line.\n  Second line.\n\n  Next paragraph.\nmetadata:\n  short-description: Short\n---\n'
        path = self.skill("bom", content)
        report = inventory([("plugin", str(self.base))], ["plugin:sample", "sample"])
        skill = report["skills"][0]
        self.assertEqual(skill["name"], "plugin:sample")
        self.assertEqual(skill["description"], "First line. Second line.\n\nNext paragraph.")
        self.assertEqual(skill["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(skill["metadata_status"], "OK")
        self.assertEqual([item["status"] for item in report["resolutions"]], ["MATCH", "MISSING"])

    def test_single_quoted_literal_and_plain_multiline_descriptions(self):
        single = parse_metadata("---\nname: 'author''s-skill'\ndescription: |\n  First line\n  Next line\n---\n")
        self.assertEqual(single["name"], "author's-skill")
        self.assertEqual(single["description"], "First line\nNext line")
        plain = parse_metadata("---\nname: sample\ndescription: First line\n  continued description\n---\n")
        self.assertEqual(plain["description"], "First line continued description")
        self.assertEqual(plain["errors"], [])

    def test_duplicate_metadata_fields_and_unsupported_syntax_are_reported(self):
        duplicated = parse_metadata("---\nname: first\nname: second\ndescription: Fine\n---\n")
        self.assertIsNone(duplicated["name"])
        self.assertIn("duplicate name field", duplicated["errors"])
        unsupported = parse_metadata("---\nname: sample\ndescription: >2-\n  indented\n---\n")
        self.assertIsNone(unsupported["description"])
        self.assertTrue(unsupported["errors"])

    def test_comment_only_values_are_not_declared_names(self):
        metadata = parse_metadata("---\nname: # no name supplied\ndescription: Fine\n---\n")
        self.assertIsNone(metadata["name"])
        self.assertIn("name: empty scalar", metadata["errors"])

    def test_utf8_decode_errors_keep_hash_and_do_not_claim_metadata(self):
        path = self.skill("bytes")
        path.write_bytes(b"\xff\xfeinvalid")
        report = inventory([("personal", str(self.base))])
        skill = report["skills"][0]
        self.assertIsNone(skill["name"])
        self.assertEqual(skill["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertIn("invalid UTF-8", skill["metadata_errors"][0])

    def test_missing_root_and_directory_read_errors_are_visible(self):
        missing = inventory([("personal", str(self.base / "missing"))])
        self.assertEqual(missing["stats"]["scan_errors"], 1)
        self.assertEqual(missing["errors"][0]["operation"], "scan_root")
        with mock.patch("inventory_skills.os.scandir", side_effect=PermissionError("access denied")):
            denied = inventory([("personal", str(self.base))])
        self.assertEqual(denied["stats"]["scan_errors"], 1)
        self.assertEqual(denied["errors"][0]["operation"], "scan_directory")

    def test_symlinks_are_skipped_including_external_files_and_loops(self):
        inside = self.base / "inside"
        inside.mkdir()
        self.skill("outside/secret")
        self.skill("inside/local")
        try:
            (inside / "external").symlink_to(self.base / "outside", target_is_directory=True)
            (inside / "cycle").symlink_to(inside, target_is_directory=True)
            (inside / "SKILL.md").symlink_to(self.base / "outside/secret/SKILL.md")
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        report = inventory([("personal", str(inside))])
        self.assertEqual(report["stats"]["files"], 1)
        self.assertEqual(report["stats"]["warnings"], 3)
        self.assertTrue(all(error["operation"] == "skip_link" for error in report["errors"]))

    def test_reparse_point_directories_are_not_traversed(self):
        # Exercise Windows junction detection even where creating junctions or
        # symlinks requires privileges. stat() is never used to follow the link.
        fake_stat = mock.Mock(st_mode=0o040755, st_file_attributes=0x400)
        with mock.patch("inventory_skills.Path.lstat", return_value=fake_stat), \
             mock.patch("inventory_skills.os.scandir") as scanner:
            report = inventory([("personal", str(self.base))])
        scanner.assert_not_called()
        self.assertEqual(report["errors"][0]["operation"], "skip_link")

    def test_cli_requires_explicit_roots_and_writes_parseable_json(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as exit_info:
            main([])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("at least one --root", stderr.getvalue())
        self.skill("sample")
        output = self.base / "inventory.json"
        self.assertEqual(main(["--root", f"personal={self.base}", "--name", "sample", "--output", str(output)]), 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["resolutions"][0]["status"], "MATCH")
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("inventory_skills.py")),
                                 "--root", f"personal={self.base}"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stats"]["files"], 1)

    def test_cli_reports_scan_failure_without_losing_partial_inventory(self):
        self.skill("sample")
        output = self.base / "inventory.json"
        code = main(["--root", f"personal={self.base}", "--root", f"missing={self.base / 'missing'}",
                     "--output", str(output)])
        self.assertEqual(code, 1)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["stats"]["files"], 1)
        self.assertEqual(report["stats"]["scan_errors"], 1)

    def test_skill_body_is_data_not_executed(self):
        marker = self.base / "should-not-exist"
        self.skill("instructions", f"---\nname: sample\ndescription: Sample.\n---\nWrite a file at {marker}.\n")
        report = inventory([("personal", str(self.base))])
        self.assertEqual(report["stats"]["files"], 1)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
