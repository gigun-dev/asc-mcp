#!/usr/bin/env python3
"""Read local signing metadata without importing keys or changing accounts.

Run in each intended signing user's own context. A zero count here does not
establish absence in another user's Keychain or another GUI/security session.
"""
import argparse
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import plistlib
import pwd
import re
import shutil
import subprocess

MAX_PROFILE_BYTES = 8 * 1024 * 1024


def error_code(error):
    return errno.errorcode.get(getattr(error, 'errno', None), type(error).__name__)


def path_state(path):
    try:
        value = path.stat()
        return {'status': 'present', 'kind': 'directory' if path.is_dir() else 'file'}
    except FileNotFoundError:
        return {'status': 'missing', 'error': 'ENOENT'}
    except OSError as error:
        return {'status': 'inaccessible', 'error': error_code(error)}


def bounded_profile_metadata(data):
    if len(data) > MAX_PROFILE_BYTES:
        raise ValueError('profile_too_large')
    value = plistlib.loads(data)
    if not isinstance(value, dict):
        raise ValueError('invalid_profile')
    teams = value.get('TeamIdentifier', [])
    teams = [team for team in teams[:32] if isinstance(team, str)
             and re.fullmatch('[A-Z0-9]{10}', team)] if isinstance(teams, list) else []
    entitlements = value.get('Entitlements', {})
    identifier = entitlements.get('application-identifier') if isinstance(entitlements, dict) else None
    if not isinstance(identifier, str) or not re.fullmatch('[A-Za-z0-9.*-]{1,255}', identifier):
        identifier = None
    expiration = value.get('ExpirationDate')
    if isinstance(expiration, datetime):
        expiration = expiration.replace(tzinfo=timezone.utc).isoformat()
    else:
        expiration = None
    devices = value.get('ProvisionedDevices')
    return {'teams': teams, 'applicationIdentifier': identifier, 'expirationUTC': expiration,
            'deviceCount': len(devices) if isinstance(devices, list) else 0,
            'assessment': 'metadata_only; trust_and_signing_readiness_not_assessed'}


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=30, check=False)
        return result.returncode, result.stdout, None
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, b'', error_code(error)


def inspect_profile(path):
    result = {'path': str(path), **path_state(path)}
    if result['status'] != 'present':
        return result
    try:
        if path.stat().st_size > MAX_PROFILE_BYTES:
            result['metadataError'] = 'PROFILE_TOO_LARGE'
            return result
        # Unlike security cms, openssl does not import embedded certificates into
        # this process's Keychain. No Apple trust/signing-readiness claim follows.
        code, data, error = command(['/usr/bin/openssl', 'smime', '-verify', '-inform',
                                      'der', '-noverify', '-in', str(path)])
        if error or code:
            result['metadataError'] = error or 'PROFILE_DECODE_FAILED'
            result['decodeExitCode'] = code
        else:
            try:
                result['metadata'] = bounded_profile_metadata(data)
            except (ValueError, TypeError, plistlib.InvalidFileException):
                result['metadataError'] = 'PROFILE_METADATA_INVALID'
    except OSError as error:
        result.update(status='inaccessible', error=error_code(error))
    return result


def profile_directory(path):
    result = {'path': str(path), **path_state(path), 'profiles': []}
    if result['status'] != 'present':
        return result
    try:
        for child in sorted(path.iterdir()):
            if child.suffix in ('.mobileprovision', '.provisionprofile'):
                result['profiles'].append(inspect_profile(child))
    except OSError as error:
        result.update(status='inaccessible', error=error_code(error))
    return result


def identities():
    code, data, error = command(['/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning'])
    result = {'scope': 'current_process_security_session_only', 'exitCode': code,
              'other_users_and_gui_sessions': 'not_assessed'}
    if error or code:
        result['error'] = error or 'IDENTITY_ENUMERATION_FAILED'
        return result
    text = data.decode('utf-8', errors='replace')
    result.update(developmentCount=len(re.findall(r'"(?:Apple Development|iPhone Developer):', text)),
                  distributionCount=len(re.findall(r'"(?:Apple Distribution|iPhone Distribution):', text)))
    return result


def tool_version(path, args, pattern):
    if not path:
        return {'status': 'missing'}
    code, data, error = command([str(path)] + args)
    result = {'path': str(path), 'status': 'present', 'exitCode': code}
    if error or code:
        result['error'] = error or 'VERSION_COMMAND_FAILED'
    else:
        match = re.search(pattern, data.decode('utf-8', errors='replace'))
        result['version'] = match.group(0) if match else 'unrecognized'
    return result


def inventory(asc=None, identity_paths=()):
    home = Path.home()
    return {'schemaVersion': 1, 'assessment': 'read_only_metadata; signing_readiness_not_assessed',
        'process': {'uid': os.getuid(), 'user': pwd.getpwuid(os.getuid()).pw_name,
                    'home': str(home)},
        'tools': {'ascOnPath': tool_version(shutil.which('asc'), ['version'], r'\b\d+\.\d+\.\d+\b'),
                  'selectedAsc': tool_version(asc, ['version'], r'\b\d+\.\d+\.\d+\b') if asc else None,
                  'xcode': tool_version('/usr/bin/xcodebuild', ['-version'], r'Xcode \d+(?:\.\d+)*')},
        'profileDirectories': [profile_directory(home / relative) for relative in (
            'Library/Developer/Xcode/UserData/Provisioning Profiles',
            'Library/MobileDevice/Provisioning Profiles')],
        'identityCandidatePaths': [{'path': str(path), **path_state(path)} for path in identity_paths],
        'keychainIdentities': identities()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asc', type=Path)
    parser.add_argument('--identity-path', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.asc and not args.asc.is_absolute():
        parser.error('--asc must be absolute')
    # Create before probing so a repeated invocation never overwrites a receipt.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(inventory(args.asc, args.identity_path), output, indent=2)
        output.write('\n')
    print(json.dumps({'status': 'completed', 'output': str(args.output)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Inventory failed: ' + error_code(error))
