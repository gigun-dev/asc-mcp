#!/usr/bin/env python3
"""Use the logged-in macOS user's security session for the official runner."""
import plistlib, sys
from pathlib import Path

root = Path(sys.argv[1]).expanduser().resolve()
plist = Path((root / '.service').read_text().strip()).expanduser().resolve()
if plist.parent != (Path.home() / 'Library/LaunchAgents').resolve():
    raise ValueError('Expected the official user LaunchAgent')
config = plistlib.loads(plist.read_bytes())
# A new security session cannot use the GUI login keychain, even when it is unlocked.
config['SessionCreate'] = False
plist.write_bytes(plistlib.dumps(config))
print('Runner uses the GUI security session; restart its service to apply')
