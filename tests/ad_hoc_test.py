import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import ad_hoc
import run


class AdHocBoundary(unittest.TestCase):
    def test_export_failure_cannot_reach_publish_and_fetch_alone_gets_source_token(self):
        calls = []
        def command(argv, cwd, env=None):
            calls.append((argv, run.child_env('build') if env is None else env))
            if argv[1:3] == ['xcode', 'export']:
                raise RuntimeError('export rejected')
        environment = {'HOME': '/home/build', 'PATH': '/tools', 'USER': 'builder', 'LOGNAME': 'builder',
                       'SOURCE_TOKEN': 'source', 'R2_ACCESS_KEY_ID': 'storage',
                       'ASC_PRIVATE_KEY': 'apple', 'UNKNOWN_SECRET': 'unknown'}
        config = {'repository': 'owner/app', 'project': 'App.xcodeproj',
                  'scheme': 'App', 'teamId': 'TEAM'}
        with patch.object(run, 'settings', return_value=config), \
             patch.object(run, 'run', side_effect=command), \
             patch.object(run.subprocess, 'check_output', return_value='a' * 40), \
             patch.dict(run.os.environ, environment, clear=True), \
             patch.object(run.sys, 'argv', ['run.py', 'app', 'a' * 40, 'b' * 36]):
            with self.assertRaises(RuntimeError):
                run.main()
        for argv, environment in calls:
            self.assertNotIn('ASC_PRIVATE_KEY', environment)
            self.assertNotIn('UNKNOWN_SECRET', environment)
            self.assertNotIn('R2_ACCESS_KEY_ID', environment)
            self.assertEqual('SOURCE_TOKEN' in environment, argv[1] == 'fetch')
            self.assertFalse(any('publish.py' in word for word in argv))

    def test_build_and_source_do_not_inherit_credentials(self):
        environment = {'HOME': '/home/build', 'PATH': '/tools', 'USER': 'builder', 'LOGNAME': 'builder',
            'R2_ACCESS_KEY_ID': 'storage-id', 'CLOUDFLARE_API_TOKEN': 'storage-key',
            'ASC_PRIVATE_KEY': 'apple-key', 'BARK_ENV': 'notification-key',
            'SOURCE_TOKEN': 'source-key', 'UNEXPECTED_SECRET': 'future-key'}
        for phase in ('build', 'source', 'sign'):
            self.assertEqual(run.child_env(phase, environment),
                             {'HOME': '/home/build', 'PATH': '/tools', 'USER': 'builder', 'LOGNAME': 'builder'})
        publish = run.child_env('publish', environment)
        self.assertIn('CLOUDFLARE_API_TOKEN', publish)
        self.assertNotIn('ASC_PRIVATE_KEY', publish)
        self.assertNotIn('SOURCE_TOKEN', publish)
        self.assertNotIn('UNEXPECTED_SECRET', publish)

    def args(self, operation, directory):
        root = Path(directory)
        common = ['--asc', sys.executable, operation, '--result', str(root/'result')]
        if operation == 'export':
            common += ['--archive', str(root/'App.xcarchive'), '--identity', str(root/'identity.p12'),
                '--password-file', str(root/'password'), '--profile', str(root/'profile'),
                '--ipa', str(root/'App.ipa'), '--team-id', 'TEAM']
        elif operation == 'prepare':
            common += ['--ipa', str(root/'App.ipa'), '--bundle-dir', str(root/'bundle'),
                '--source-revision', 'a'*40, '--channel', 'mini-route-test']
        else:
            common += ['--bundle-dir', str(root/'bundle'), '--endpoint', 'https://objects.example',
                '--region', 'auto', '--bucket', 'private', '--prefix', 'mini-route-test']
        return ad_hoc.parser().parse_args(common)

    def bundle(self, directory):
        root = Path(directory)/'bundle'
        (root/'payload').mkdir(parents=True)
        (root/'payload/app.ipa').write_text('untrusted fixture, ASC must verify')
        (root/'bundle.json').write_text('{}')

    def test_export_has_fixed_child_and_no_account_or_publish_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            phase, command = ad_hoc.commands(self.args('export', directory))[0]
        self.assertEqual(phase, 'export')
        child = command[command.index('--')+1:]
        self.assertEqual(child[:3], [sys.executable, 'xcode', 'export'])
        self.assertEqual(child[child.index('--method')+1], 'release-testing')
        self.assertEqual(child[child.index('--signing-style')+1], 'manual')
        self.assertNotIn('-allowProvisioningUpdates', command)
        self.assertNotIn('--export-options', command)
        self.assertNotIn('publish', command)

    def test_only_publish_receives_storage_credentials(self):
        source = {'HOME': '/home/sign', 'USER': 'signer', 'LOGNAME': 'signer',
            'ASC_PRIVATE_KEY': 'apple', 'ASC_S3_SECRET_ACCESS_KEY': 'storage',
            'CLOUDFLARE_API_TOKEN': 'legacy', 'BARK_ENV': 'bark', 'SOURCE_TOKEN': 'source'}
        for phase in ('export', 'prepare'):
            self.assertEqual(ad_hoc.distribution_env(phase, source),
                             {'HOME': '/home/sign', 'USER': 'signer', 'LOGNAME': 'signer'})
        publish = ad_hoc.distribution_env('publish', source)
        self.assertEqual(publish['ASC_S3_SECRET_ACCESS_KEY'], 'storage')
        for key in ('ASC_PRIVATE_KEY','CLOUDFLARE_API_TOKEN','BARK_ENV','SOURCE_TOKEN'):
            self.assertNotIn(key, publish)

    def test_publish_rejects_missing_bundle_before_any_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ad_hoc.subprocess, 'run') as process:
                with self.assertRaises(ValueError):
                    ad_hoc.execute(self.args('publish', directory))
                process.assert_not_called()

    def test_ipa_validation_failure_prevents_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            self.bundle(directory)
            with patch.object(ad_hoc.subprocess, 'run') as process:
                process.return_value.returncode = 1
                with self.assertRaises(RuntimeError):
                    ad_hoc.execute(self.args('publish', directory))
                process.assert_called_once()
                command = process.call_args.args[0]
                self.assertEqual(command[1:3], ['distribute', 'prepare'])
                self.assertNotIn('ASC_S3_SECRET_ACCESS_KEY', process.call_args.kwargs['env'])

    def test_publish_private_lifetime_is_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            self.bundle(directory)
            command = ad_hoc.commands(self.args('publish', directory), Path(directory)/'verify')[1][1]
        for flag, value in [('--access','private'),('--url-ttl','24h'),('--download-grace','1h')]:
            self.assertEqual(command[command.index(flag)+1], value)
        self.assertNotIn('--public-base-url', command)

    def test_receipts_are_private_create_only_and_failure_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args('export', directory)
            receipt = args.result
            with patch.object(ad_hoc.subprocess, 'run') as process:
                process.return_value.returncode = 1
                with self.assertRaises(RuntimeError):
                    ad_hoc.execute(args)
                process.assert_called_once()
                self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
                self.assertEqual(Path(str(receipt) + '.stderr').stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    ad_hoc.execute(args)
                process.assert_called_once()


if __name__ == '__main__':
    unittest.main()
