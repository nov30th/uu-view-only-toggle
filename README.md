# UU View-Only Toggle

A tiny Windows utility that adds a real **view-only mode** to NetEase UU Remote (网易UU远程), preventing local mouse/keyboard input from being forwarded to the controlled machine while the screen continues to render normally.

## Why

UU Remote does not expose an obvious view-only toggle on the Windows client. This tool bridges that gap without touching UU's process memory, without DLL injection, and without low-level system hooks — it uses one tiny Win32 API call: `EnableWindow`.

## How it works

1. Enumerates all visible top-level windows owned by `GameViewer.exe` (the actual UU Remote process).
2. Lets you pick which window(s) to control.
3. On hotkey, walks all child windows of the chosen targets and calls `EnableWindow(hwnd, FALSE)`.
4. Windows itself drops mouse and keyboard messages before they ever reach UU's render surface.
5. The top-level window stays enabled, so you can still drag, minimize, and close UU normally.

No admin rights required. No global hooks. No third-party Python dependencies.

## Files

| File | Purpose |
|------|---------|
| `uu_view_only.py` | The toggle script (pure `ctypes`, stdlib only) |
| `run_uu_view_only.bat` | Double-click launcher |
| `docs/research.md` | Background research on alternative approaches |

## Requirements

- Windows 10 / 11
- Python 3.10+ in `PATH`
- NetEase UU Remote installed and running (`GameViewer.exe`)

## Usage

1. Open UU Remote and connect to a remote machine.
2. Double-click `run_uu_view_only.bat`.
3. The console prints all `GameViewer.exe` windows. Press Enter to target them all, or type a comma list (e.g. `1,3`).
4. Use the hotkeys:

| Hotkey | Action |
|--------|--------|
| `Ctrl+Alt+V` | Toggle view-only / control mode |
| `Ctrl+Alt+B` | Rescan and re-pick target windows |
| `Ctrl+C` | Exit (auto-restores enabled state) |

## Known caveats

- In view-only mode, UU's own toolbar buttons (screenshot, resolution, etc.) are also disabled, because they are child windows. Press `Ctrl+Alt+V` to come back to control mode before using them.
- If the UU window is closed and reopened, the cached handle becomes invalid. Press `Ctrl+Alt+B` to rescan.
- If UU ever ships a built-in view-only mode on Windows, prefer that — this tool is a workaround.

## Configuration

Edit the top of `uu_view_only.py` to target a different process:

```python
TARGET_EXE = "GameViewer.exe"
```

## License

MIT
