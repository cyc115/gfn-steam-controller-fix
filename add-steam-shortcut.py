#!/usr/bin/env python3
"""Add the patched GFN copy to Steam as a non-Steam game.

Steam applies a per-game controller layout (back buttons, gyro, ...) only to
processes it starts itself. The shortcut targets the executable inside the
bundle, not the .app: an .app target is started through LaunchServices, Steam
loses the process, and the Desktop layout applies instead.

Preview by default; --apply writes. Steam must be quit first, since it rewrites
shortcuts.vdf on exit. The original file is backed up before any change.
"""

import argparse
import datetime
import os
import random
import shutil
import struct
import subprocess
import sys
from pathlib import Path

STEAM = Path.home() / 'Library/Application Support/Steam'
APP = Path('/Applications/GeForceNOW-Steam-Controller.app')
NAME = 'GeForce NOW (Steam Controller)'
BACKUPS = Path.home() / 'Library/Application Support/gfn-steam-controller-fix/backups'

MAP, STR, INT, END = 0, 1, 2, 8


# --- Binary KeyValues (shortcuts.vdf): ordered (key, value) lists -------------

def parse(data):
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b'\0', pos)
        text = data[pos:end].decode('utf-8')
        pos = end + 1
        return text

    def obj():
        nonlocal pos
        pairs = []
        while True:
            kind = data[pos]
            pos += 1
            if kind == END:
                return pairs
            key = cstr()
            if kind == MAP:
                pairs.append((key, obj()))
            elif kind == STR:
                pairs.append((key, cstr()))
            elif kind == INT:
                pairs.append((key, struct.unpack_from('<I', data, pos)[0]))
                pos += 4
            else:
                raise ValueError(f'unsupported field type {kind} at byte {pos - 1}')

    root = obj()
    if pos != len(data):
        raise ValueError('trailing bytes after shortcuts.vdf root')
    return root


def dump(pairs):
    out = bytearray()
    for key, value in pairs:
        name = key.encode('utf-8') + b'\0'
        if isinstance(value, list):
            out += bytes([MAP]) + name + dump(value)
        elif isinstance(value, int):
            out += bytes([INT]) + name + struct.pack('<I', value)
        else:
            out += bytes([STR]) + name + value.encode('utf-8') + b'\0'
    return bytes(out + bytes([END]))


def shortcuts_of(root):
    for key, value in root:
        if key.lower() == 'shortcuts':
            return value
    raise ValueError('shortcuts.vdf has no "shortcuts" map')


def field(entry, name):
    return next((v for k, v in entry if k.lower() == name.lower()), None)


def new_entry(appid, name, exe):
    start_dir = str(Path(exe).parent) + '/'
    return [
        ('appid', appid), ('AppName', name), ('Exe', f'"{exe}"'),
        ('StartDir', start_dir), ('icon', ''), ('ShortcutPath', ''),
        ('LaunchOptions', ''), ('IsHidden', 0), ('AllowDesktopConfig', 1),
        ('AllowOverlay', 1), ('OpenVR', 0), ('Devkit', 0), ('DevkitGameID', ''),
        ('DevkitOverrideAppID', 0), ('LastPlayTime', 0), ('FlatpakAppID', ''),
        ('sortas', ''), ('tags', []),
    ]


def add_shortcut(root, name, exe, rng=random):
    """Return (root, appid, added). Idempotent on the Exe target."""
    shortcuts = shortcuts_of(root)
    quoted = f'"{exe}"'
    for _, entry in shortcuts:
        if field(entry, 'Exe') in (quoted, exe):
            return root, field(entry, 'appid'), False
    used = {field(entry, 'appid') for _, entry in shortcuts}
    # Current Steam assigns non-Steam shortcuts a random 32-bit id with the top
    # bit set; it is what the controller config and grid art key on.
    appid = next(a for a in iter(lambda: rng.getrandbits(31) | 0x80000000, None) if a not in used)
    index = max((int(k) for k, _ in shortcuts if k.isdigit()), default=-1) + 1
    shortcuts.append((str(index), new_entry(appid, name, exe)))
    return root, appid, True


# --- Steam account discovery -------------------------------------------------

def most_recent_account():
    """Account ID (userdata folder) of the most recently signed-in Steam user."""
    text = (STEAM / 'config/loginusers.vdf').read_text(errors='replace')
    best, best_ts, current = None, -1, None
    for raw in text.splitlines():
        parts = [p for p in raw.strip().split('"') if p.strip()]
        if len(parts) == 1 and parts[0].isdigit() and len(parts[0]) == 17:
            current = int(parts[0]) - 76561197960265728
        elif len(parts) == 2 and current is not None:
            if parts[0].lower() == 'mostrecent' and parts[1] == '1':
                return str(current)
            if parts[0].lower() == 'timestamp' and int(parts[1]) > best_ts:
                best, best_ts = str(current), int(parts[1])
    if best is None:
        raise SystemExit('No Steam account found in loginusers.vdf; sign in to Steam once.')
    return best


def steam_running():
    result = subprocess.run(['pgrep', '-x', 'steam_osx'], capture_output=True)
    return result.returncode == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='write the change (default: preview only)')
    ap.add_argument('--account', help='Steam account ID (userdata folder); default: most recent sign-in')
    ap.add_argument('--app', type=Path, default=APP, help=f'patched GFN bundle (default: {APP})')
    ap.add_argument('--name', default=NAME, help=f'shortcut name in Steam (default: {NAME!r})')
    args = ap.parse_args(argv)

    exe = args.app / 'Contents/MacOS/GeForceNOW'
    if not os.access(exe, os.X_OK):
        raise SystemExit(f'{exe} not found or not executable; run ./install.zsh first.')
    account = args.account or most_recent_account()
    vdf = STEAM / 'userdata' / account / 'config/shortcuts.vdf'
    original = vdf.read_bytes() if vdf.exists() else dump([('shortcuts', [])])

    root, appid, added = add_shortcut(parse(original), args.name, str(exe))
    print(f'account:  {account}')
    print(f'file:     {vdf}')
    print(f'target:   {exe}')
    print(f'appid:    {appid}')
    if not added:
        print('Shortcut already present; nothing to do.')
        return 0
    if not args.apply:
        print(f'Would add {args.name!r}. Quit Steam, then rerun with --apply.')
        return 0
    if steam_running():
        raise SystemExit('Steam is running and would overwrite shortcuts.vdf on exit. Quit Steam first.')

    data = dump(root)
    if parse(data) != root:
        raise SystemExit('Internal error: serialized shortcuts.vdf does not read back.')
    backup = BACKUPS / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-shortcuts')
    backup.mkdir(parents=True, mode=0o700)
    if vdf.exists():
        shutil.copy2(vdf, backup / 'shortcuts.vdf')
    vdf.parent.mkdir(parents=True, exist_ok=True)
    tmp = vdf.with_name(vdf.name + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, vdf)
    if vdf.read_bytes() != data:
        raise SystemExit(f'Readback mismatch; original kept in {backup}')
    print(f'Added {args.name!r}. Backup: {backup}')
    print('Open Steam, launch the shortcut, then Controller settings -> Edit Layout -> back buttons.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
