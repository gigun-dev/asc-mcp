#!/usr/bin/env python3
"""Separate local Ad Hoc export, verification, and explicit private publication.

Uses ASC's signing run/prepare/publish primitives without Apple API credentials.
Executor identities and artifact handoff remain the operator's responsibility.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from run import child_env

S3_ENV = frozenset(('ASC_S3_ACCESS_KEY_ID', 'ASC_S3_SECRET_ACCESS_KEY',
                    'ASC_S3_SESSION_TOKEN'))


def distribution_env(phase, environ=None):
    source = os.environ if environ is None else environ
    result = child_env('sign', source)
    if phase == 'publish':
        result.update({key: value for key, value in source.items() if key in S3_ENV})
    return result


def commands(args, verification_dir=None):
    asc = Path(args.asc)
    if not asc.is_absolute() or not asc.is_file():
        raise ValueError('An existing absolute ASC binary path is required')
    asc = str(asc)
    if args.operation == 'export':
        return [('export', [asc, 'signing', 'run', '--identity', str(args.identity),
            '--identity-password-file', str(args.password_file), '--profile', str(args.profile),
            '--purpose', 'release-testing', '--receipt', str(args.result) + '.signing.json',
            '--', asc, 'xcode', 'export', '--archive-path', str(args.archive),
            '--ipa-path', str(args.ipa), '--method', 'release-testing',
            '--signing-style', 'manual', '--team-id', args.team_id, '--output', 'json'])]
    if args.operation == 'prepare':
        if not re.fullmatch('[a-f0-9]{40}', args.source_revision):
            raise ValueError('An exact source commit is required')
        return [('prepare', [asc, 'distribute', 'prepare', '--ipa', str(args.ipa),
            '--output-dir', str(args.bundle_dir), '--source-revision', args.source_revision,
            '--channel', args.channel, '--output', 'json'])]
    # An arbitrary directory is never treated as a verified bundle. ASC prepares
    # its payload again locally, then ASC publish validates the original bundle
    # descriptor/payload binding. No storage credential reaches the verification.
    ipa = args.bundle_dir / 'payload/app.ipa'
    if not (args.bundle_dir / 'bundle.json').is_file() or not ipa.is_file():
        raise ValueError('An ASC prepared bundle is required')
    if verification_dir is None:
        raise ValueError('A private verification directory is required')
    return [('prepare', [asc, 'distribute', 'prepare', '--ipa', str(ipa),
                '--output-dir', str(verification_dir / 'bundle'), '--output', 'json']),
            ('publish', [asc, 'distribute', 'publish', '--bundle-dir', str(args.bundle_dir),
                '--endpoint', args.endpoint, '--region', args.region,
                '--bucket', args.bucket, '--prefix', args.prefix,
                '--access', 'private', '--url-ttl', '24h', '--download-grace', '1h',
                '--receipt', str(args.result) + '.publish.json',
                '--link-path', str(args.result) + '.link.json', '--output', 'json'])]


def execute(args):
    with tempfile.TemporaryDirectory(prefix='asc-ipa-verification-') as temporary:
        sequence = commands(args, Path(temporary))
        # Exact private URLs and diagnostics stay in create-only private files.
        fd = os.open(args.result, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            error_fd = os.open(str(args.result) + '.stderr',
                               os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(error_fd, 'wb') as errors:
                for phase, command in sequence:
                    result = subprocess.run(command, env=distribution_env(phase),
                                            stdout=output, stderr=errors, check=False)
                    if result.returncode:
                        raise RuntimeError('ASC ' + phase + ' failed (exit '
                                           + str(result.returncode) + ')')
    return {'operation': args.operation, 'status': 'completed', 'result': str(args.result)}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asc', required=True, help='Approved absolute ASC binary path on executor')
    sub = p.add_subparsers(dest='operation', required=True)
    export = sub.add_parser('export', help='Temporary signing identity; fixed manual local export')
    for name in ('archive', 'identity', 'password-file', 'profile', 'ipa'):
        export.add_argument('--' + name, type=Path, required=True)
    export.add_argument('--team-id', required=True)
    prepare = sub.add_parser('prepare', help='Local ASC IPA validation and immutable bundle')
    prepare.add_argument('--ipa', type=Path, required=True)
    prepare.add_argument('--bundle-dir', type=Path, required=True)
    prepare.add_argument('--source-revision', required=True)
    prepare.add_argument('--channel', required=True)
    publish = sub.add_parser('publish', help='Reverify IPA, then explicitly publish private links')
    publish.add_argument('--bundle-dir', type=Path, required=True)
    for name in ('endpoint', 'region', 'bucket', 'prefix'):
        publish.add_argument('--' + name, required=True)
    for operation in (export, prepare, publish):
        operation.add_argument('--result', type=Path, required=True,
                               help='Create-only private ASC stdout and adjacent receipts')
    return p


if __name__ == '__main__':
    try:
        print(json.dumps(execute(parser().parse_args())))
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(type(error).__name__ + ': Ad Hoc operation did not complete; inspect private diagnostics')
