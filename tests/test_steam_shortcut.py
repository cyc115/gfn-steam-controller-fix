import importlib.util
import random
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'add_steam_shortcut', Path(__file__).resolve().parent.parent / 'add-steam-shortcut.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

EXE = '/Applications/GeForceNOW-Steam-Controller.app/Contents/MacOS/GeForceNOW'


def existing_file():
    entry = mod.new_entry(0xCD4A9814, 'GeForceNOW', '/Applications/GeForceNOW.app')
    return mod.dump([('shortcuts', [('0', entry)])])


def test_round_trip_is_byte_exact():
    data = existing_file()
    assert mod.dump(mod.parse(data)) == data


def test_add_appends_quoted_target_with_high_bit_appid():
    root, appid, added = mod.add_shortcut(mod.parse(existing_file()), 'GFN', EXE, random.Random(1))
    shortcuts = mod.shortcuts_of(root)
    assert added and len(shortcuts) == 2
    key, entry = shortcuts[1]
    assert key == '1'
    assert mod.field(entry, 'Exe') == f'"{EXE}"'
    assert mod.field(entry, 'StartDir') == str(Path(EXE).parent) + '/'
    assert appid & 0x80000000 and appid != 0xCD4A9814
    assert mod.parse(mod.dump(root)) == root


def test_add_is_idempotent():
    root, appid, _ = mod.add_shortcut(mod.parse(existing_file()), 'GFN', EXE)
    again, same, added = mod.add_shortcut(mod.parse(mod.dump(root)), 'GFN', EXE)
    assert not added and same == appid
    assert len(mod.shortcuts_of(again)) == 2


def test_parses_real_steam_layout_bytes():
    # Shape copied from a Steam-written file: nested empty "tags" map, then END x3.
    data = (b'\x00shortcuts\x00\x000\x00\x02appid\x00\x14\x98\x4a\xcd'
            b'\x01AppName\x00GeForceNOW\x00\x00tags\x00\x08\x08\x08\x08')
    root = mod.parse(data)
    assert mod.field(mod.shortcuts_of(root)[0][1], 'appid') == 0xCD4A9814
    assert mod.dump(root) == data
