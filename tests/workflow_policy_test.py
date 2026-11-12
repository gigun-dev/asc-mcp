import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPolicyTest(unittest.TestCase):
    def test_node_security_patches_follow_supported_major(self):
        for name in ("build.yml", "check.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text()
            self.assertIn("node-version: 24\n", workflow)
            self.assertIn("check-latest: true\n", workflow)
            self.assertNotIn("node-version: 24.", workflow)


if __name__ == "__main__":
    unittest.main()
