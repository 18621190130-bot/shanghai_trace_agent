import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools/demos/demo.py"), *([] if "--data" in args else ["--data",str(ROOT/"data/archive/pois_pre_phase2_5.json")]), *args],
                              cwd=ROOT.parent, capture_output=True, encoding="utf-8", timeout=30)

    def test_all_examples_and_saved_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "plans.json"
            process = self.run_cli("--json", "--output", str(output))
            self.assertEqual(process.returncode, 0, process.stderr)
            payload = json.loads(process.stdout)
            self.assertEqual(payload, json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(len(payload["examples"]), 5)
            self.assertTrue(all(p["status"] == "success" for p in payload["examples"].values()))

    def test_structured_custom_request(self):
        process = self.run_cli("--json", "--request", str(ROOT / "examples" / "request.json"))
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertEqual(payload["status"], "success")
        self.assertIn("p13", [n["poi_id"] for n in payload["ordered_pois"]])

    def test_invalid_input_returns_nonzero_and_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            request = Path(folder) / "request.json"
            request.write_text(json.dumps({"available_minutes": 180, "interest_tags": ["invented"]}), encoding="utf-8")
            process = self.run_cli("--json", "--request", str(request))
            self.assertEqual(process.returncode, 2)
            payload = json.loads(process.stdout)
            self.assertEqual(payload["status"], "validation_error")
            self.assertIn("invented", payload["errors"][0])

    def test_invalid_json_and_data_have_clear_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            request = Path(folder) / "request.json"
            request.write_text("{broken", encoding="utf-8")
            process = self.run_cli("--json", "--request", str(request))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stderr)["status"], "validation_error")
            process = self.run_cli("--json", "--data", str(Path(folder) / "missing.json"))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stderr)["status"], "validation_error")
