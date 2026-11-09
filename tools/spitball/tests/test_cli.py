import json
import subprocess
import sys
import unittest


def run_cli(args, payload):
    proc = subprocess.run(
        [sys.executable, "-m", "tools.spitball", *args],
        input=json.dumps(payload), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestCli(unittest.TestCase):
    def test_obvious_subcommand(self):
        # "literal" 3/5 = 0.60 >= 0.25 -> obvious; "rare" 1/5 = 0.20 < 0.25 -> excluded.
        payload = {"panelists": [
            {"clusters": ["literal"]}, {"clusters": ["literal"]},
            {"clusters": ["literal"]}, {"clusters": ["rare"]},
            {"clusters": []},
        ]}
        out = run_cli(["obvious"], payload)
        labels = [o["label"] for o in out["obvious_clusters"]]
        self.assertEqual(labels, ["literal"])            # 3/5 = 0.60

    def test_rank_subcommand(self):
        payload = {"candidates": [
            {"text": "A", "value_score": 0.9, "fringe_proximity": 0.4,
             "nearest_obvious_cluster": None},
            {"text": "B", "value_score": 0.7, "fringe_proximity": 0.9,
             "nearest_obvious_cluster": None},
        ]}
        out = run_cli(["rank", "--k", "2"], payload)
        self.assertEqual([c["text"] for c in out["ranked"]], ["B", "A"])

    def test_fringe_check_subcommand(self):
        payload = {
            "predicates": ["COOLING", "HEAD"],
            "answers": [
                {"panelist": 0, "value_score": 0.9},
                {"panelist": 1, "value_score": 0.4, "cluster": "cold-not-cranial"},
                {"panelist": 2, "value_score": 0.4, "cluster": "wearable-gadget"},
            ],
            "clusters": [
                {"label": "cold-not-cranial", "drops": "HEAD"},
                {"label": "wearable-gadget", "drops": "WEARABLE"},
            ],
        }
        out = run_cli(["fringe-check"], payload)
        self.assertEqual(out["near_miss"], 2)
        self.assertEqual(out["unmatched"], ["wearable-gadget"])  # JSON tuple -> list

    def test_rank_missing_field_exits_2_with_message(self):
        proc = subprocess.run([sys.executable, "-m", "tools.spitball", "rank"],
            input=json.dumps({"candidates": [{"text": "A", "value_score": 0.8,
                                              "nearest_obvious_cluster": None}]}),
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing fringe_proximity", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_rank_without_candidates_key_exits_2(self):
        proc = subprocess.run([sys.executable, "-m", "tools.spitball", "rank"],
                              input="{}", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("candidates", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
