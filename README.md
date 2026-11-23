# Steam Controller (2026) gamepad fix for GeForce NOW on macOS

If your Steam Controller works in the GeForce NOW menu or as mouse and keyboard
input but is not detected as a gamepad in streamed games, this project fixes
it. Unmodified GFN takes Steam's virtual Xbox controller through Apple's
`GameController.framework` and does not deliver usable input to the stream. The
installer builds a separate, locally signed copy of GFN with that backend
disabled, so GFN reads the controller through its HID backend, and adds a small
bridge that sends vibration to the physical controller. The official app is not
modified, and SIP stays enabled. [Technical notes](docs/technical-notes.md)
describe the mechanism and evidence.

> [!WARNING]
> This is an independent workaround, not an NVIDIA or Valve product. Using a
> modified GeForce NOW client may violate the
> [GeForce NOW Terms of Use](https://www.nvidia.com/en-us/geforce-now/terms-of-use/)
> and may result in suspension or termination of your GFN account.

Tested end to end, including vibration, with GFN `2.0.88.129` on macOS `26.5.2`
(Mac mini M4) and Steam Controller `28de:1304`. GFN `2.0.86.124`,
`2.0.87.130`/`2.0.87.131`, `2.0.89.154` and `2.0.90.126` also match the build's instruction
signatures; for any other version the build stops before anything is installed.

## Install

You need an Apple Silicon Mac, the official GeForce NOW app in `/Applications`,
Steam running with a controller layout that emits gamepad controls, and Xcode
Command Line Tools (`xcode-select --install`).

```sh
git clone https://github.com/mikeqwe/gfn-steam-controller-fix.git
cd gfn-steam-controller-fix
./install.zsh
```

The installer may ask for an administrator password. It adds
`GeForceNOW-Steam-Controller` to Applications: open it for Steam Controller
sessions, and keep the official app as the source for rebuilds. For vibration,
enable GeForce NOW under **System Settings → Privacy & Security → Input
Monitoring** after the first launch, then reopen the app.

## Custom controller layout (back buttons, gyro)

Steam applies a game's own controller layout only to apps it starts itself.
To remap the back buttons (L4/R4/L5/R5) or gyro for GFN alone, add the patched
copy to Steam, then quit Steam and run:

```sh
./add-steam-shortcut.py           # preview
./add-steam-shortcut.py --apply
```

It adds `GeForce NOW (Steam Controller)` to the most recently signed-in
account (`--account` to pick another), targeting the executable inside the
bundle: a `.app` target is started through LaunchServices, Steam loses the
process, and the Desktop layout applies instead. The original `shortcuts.vdf`
is backed up under
`~/Library/Application Support/gfn-steam-controller-fix/backups/`.

Launch GFN from that shortcut, then open its **Controller settings → Edit
Layout → Buttons** and bind the back buttons. GFN sees a standard Xbox pad, so
a back button can be any Xbox button, a keyboard key or mouse action (for
games that accept mixed input), or a Steam action such as hold-for-gyro.

## Update

GFN updates remove the patch. After each one, quit GeForce NOW and run:

```sh
git pull
./install.zsh
```

If the build stops with `unexpected instructions`, `unexpected function bytes`,
or `Unexpected Forge rumble function layout`, this GFN version is not supported
yet and nothing was replaced. Open an
[issue](https://github.com/mikeqwe/gfn-steam-controller-fix/issues/new/choose)
with the GFN version and the installer output.

## Troubleshooting

Quit every GeForce NOW window before running the scripts below.

- **Gamepad still not detected in games:** make sure you opened
  `GeForceNOW-Steam-Controller`, not the official app, and run `./verify.zsh`.
- **Input works, but no vibration:** run `./repair-input-monitoring.zsh`,
  enable GeForce NOW in the Input Monitoring pane it opens, and reopen the app.
- **"Problem Detected" after launch:** a background process of the other GFN
  copy is still running. Run `./reset-gfn-container.zsh` and open the app
  again.

## Limitations

- `GameController.framework` is disabled for every controller in the patched
  copy, so other controllers may lose platform-specific behavior.
- Only a physical Steam Controller at GFN controller ID 0 vibrates; other
  gamepads get no vibration, and trigger haptics are ignored.

## Uninstall

`./uninstall.zsh` removes `/Applications/GeForceNOW-Steam-Controller.app` and
nothing else.

## License

[MIT](LICENSE). GeForce NOW, NVIDIA, Steam, Valve, Xbox, Apple, and macOS are
trademarks of their respective owners.
