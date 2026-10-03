import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('runner',Path(__file__).resolve().parents[1]/'scripts/run.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class RunnerSettings(unittest.TestCase):
 def test_no_path_escape_or_argv_option(self):
  with tempfile.TemporaryDirectory() as directory:
   config=Path(directory)/'projects.json'
   for path in ['../evil.xcodeproj','/tmp/evil.xcodeproj','-bad']:
    config.write_text(json.dumps({'app':{'repository':'owner/app','project':path,'scheme':'App','teamId':'TEAM'}}))
    with self.assertRaises(ValueError):runner.settings(config,'app','a'*40,'a'*36)
 def test_exact_sha_required(self):
  with self.assertRaises(ValueError):runner.settings('missing','app','main','a'*36)
