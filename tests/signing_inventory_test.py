import importlib.util
from datetime import datetime
import errno
from pathlib import Path
import plistlib
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('signing_inventory',
    Path(__file__).resolve().parents[1]/'scripts/signing_inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class SigningInventory(unittest.TestCase):
    def test_permission_denied_is_not_missing(self):
        with patch.object(Path, 'stat', side_effect=PermissionError(errno.EACCES, 'sensitive path')):
            result = inventory.path_state(Path('/protected/identity.p12'))
        self.assertEqual(result, {'status': 'inaccessible', 'error': 'EACCES'})
        self.assertNotIn('sensitive', str(result))
        with patch.object(Path, 'stat', side_effect=FileNotFoundError(errno.ENOENT, 'missing')):
            self.assertEqual(inventory.path_state(Path('/missing'))['status'], 'missing')

    def test_profile_output_contains_only_bounded_metadata(self):
        raw = plistlib.dumps({'Name': 'private profile name', 'UUID': 'private uuid',
            'TeamIdentifier': ['KK42DL23GH'], 'ExpirationDate': datetime(2027, 2, 13),
            'ProvisionedDevices': ['raw-device-one', 'raw-device-two'],
            'DeveloperCertificates': [b'certificate'],
            'Entitlements': {'application-identifier': 'KK42DL23GH.dev.gigun.miniroutetest',
                             'private-key-like-field': 'secret'}})
        result = inventory.bounded_profile_metadata(raw)
        self.assertEqual(result['deviceCount'], 2)
        self.assertEqual(result['teams'], ['KK42DL23GH'])
        self.assertEqual(result['applicationIdentifier'], 'KK42DL23GH.dev.gigun.miniroutetest')
        self.assertEqual(result['expirationUTC'], '2027-02-13T00:00:00+00:00')
        for private in ('raw-device', 'private profile', 'private uuid', 'certificate', 'secret'):
            self.assertNotIn(private, str(result))

    def test_identity_output_counts_only_current_context(self):
        raw = b'1) ABC "Apple Development: Name (TEAM)"\n2) DEF "Apple Distribution: Org (TEAM)"\n'
        with patch.object(inventory, 'command', return_value=(0, raw, None)):
            result = inventory.identities()
        self.assertEqual(result['developmentCount'], 1)
        self.assertEqual(result['distributionCount'], 1)
        self.assertEqual(result['other_users_and_gui_sessions'], 'not_assessed')
        self.assertNotIn('Name', str(result))
        self.assertNotIn('Org', str(result))


if __name__ == '__main__':
    unittest.main()
