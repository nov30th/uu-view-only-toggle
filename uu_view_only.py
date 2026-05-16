"""
UU Remote View-Only Toggle  (Plan C: EnableWindow)

Filters by process name (default: GameViewer.exe — the real UU Remote exe).
On startup lists all matching top-level windows and lets you pick which to control.

Hotkeys:
  Ctrl+Alt+V   toggle view-only / control mode
  Ctrl+Alt+B   rescan and re-pick target windows
  Ctrl+C       exit (auto-restore enabled state)

Notes:
  - In view-only mode, UU's own toolbar buttons (screenshot, resolution, etc.) are
    also disabled because they are child windows. Press Ctrl+Alt+V to come back.
  - The top-level window itself stays enabled, so you can still drag / close it.
"""

import ctypes
import signal
import sys
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Change here if you want a different target process
TARGET_EXE = "GameViewer.exe"

# ---------- Win32 signatures ----------
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.EnableWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.PostQuitMessage.argtypes = [ctypes.c_int]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_V = 0x56
VK_B = 0x42
WM_HOTKEY = 0x0312
HOTKEY_TOGGLE = 1
HOTKEY_RESCAN = 2


def get_window_title(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def get_window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_window_size(hwnd: int) -> tuple[int, int]:
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return (0, 0)
    return (r.right - r.left, r.bottom - r.top)


def get_process_exe(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == 0:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
        return ""
    finally:
        kernel32.CloseHandle(h)


def find_target_windows() -> list[int]:
    """Visible top-level windows whose owning process exe matches TARGET_EXE."""
    matches: list[int] = []

    @EnumWindowsProc
    def cb(hwnd, _lp):
        if user32.IsWindowVisible(hwnd):
            exe = get_process_exe(hwnd)
            if exe.lower() == TARGET_EXE.lower():
                matches.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return matches


def collect_descendants(parent: int) -> list[int]:
    desc: list[int] = []

    @EnumWindowsProc
    def cb(hwnd, _lp):
        desc.append(hwnd)
        return True

    user32.EnumChildWindows(parent, cb, 0)
    return desc


def print_window_list(windows: list[int]) -> None:
    for i, hwnd in enumerate(windows, 1):
        title = get_window_title(hwnd) or "(no title)"
        cls = get_window_class(hwnd)
        w, h = get_window_size(hwnd)
        print(f"  [{i}] HWND=0x{hwnd:08X}  size={w}x{h}  class={cls}")
        print(f"      title: {title}")


def prompt_selection(windows: list[int]) -> list[int]:
    if not windows:
        return []
    print()
    print(f"Found {len(windows)} window(s) belonging to {TARGET_EXE}:")
    print_window_list(windows)
    print()
    raw = input("Pick targets [Enter = ALL, or e.g. '1' or '1,3']: ").strip()
    if not raw:
        return windows
    try:
        idx = [int(x) for x in raw.replace(" ", "").split(",")]
        picked = [windows[i - 1] for i in idx if 1 <= i <= len(windows)]
        if not picked:
            print("[WARN] No valid index, applying to ALL.")
            return windows
        return picked
    except ValueError:
        print("[WARN] Invalid input, applying to ALL.")
        return windows


def apply_mode(selected: list[int], view_only: bool) -> list[int]:
    alive = [h for h in selected if user32.IsWindow(h)]
    dead = len(selected) - len(alive)
    if dead:
        print(f"[WARN] {dead} target window(s) no longer exist. Press Ctrl+Alt+B to rescan.")
    enable = wintypes.BOOL(not view_only)
    affected = 0
    for top in alive:
        for child in collect_descendants(top):
            user32.EnableWindow(child, enable)
            affected += 1
    mode = "VIEW-ONLY (input blocked)" if view_only else "CONTROL (normal)"
    print(f"[OK] Mode: {mode}  | top windows: {len(alive)}  | children affected: {affected}")
    return alive


def main() -> int:
    print("===================================================")
    print(f"  UU View-Only Toggle   (filter: process == {TARGET_EXE})")
    print("  Hotkeys:")
    print("    Ctrl+Alt+V  toggle view-only / control")
    print("    Ctrl+Alt+B  rescan and re-pick target windows")
    print("    Ctrl+C      exit (auto-restore)")
    print("===================================================")

    windows = find_target_windows()
    if not windows:
        print(f"[ERR] No visible window of {TARGET_EXE} found.")
        print("      Make sure UU Remote is running and a remote session is open.")
        input("Press Enter to exit...")
        return 1

    selected = prompt_selection(windows)
    print(f"[OK] Tracking {len(selected)} window(s). Hotkey ready.")

    if not user32.RegisterHotKey(None, HOTKEY_TOGGLE, MOD_CONTROL | MOD_ALT, VK_V):
        print(f"[ERR] Register Ctrl+Alt+V failed (Win32 error {ctypes.get_last_error()}).")
        return 1
    if not user32.RegisterHotKey(None, HOTKEY_RESCAN, MOD_CONTROL | MOD_ALT, VK_B):
        print(f"[WARN] Register Ctrl+Alt+B failed (Win32 error {ctypes.get_last_error()}); rescan unavailable.")

    signal.signal(signal.SIGINT, lambda *_: user32.PostQuitMessage(0))

    state = {"view_only": False, "selected": selected}
    msg = wintypes.MSG()
    try:
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message != WM_HOTKEY:
                continue
            if msg.wParam == HOTKEY_TOGGLE:
                state["view_only"] = not state["view_only"]
                state["selected"] = apply_mode(state["selected"], state["view_only"])
            elif msg.wParam == HOTKEY_RESCAN:
                print("[INFO] Rescanning...")
                if state["view_only"]:
                    apply_mode(state["selected"], False)
                    state["view_only"] = False
                fresh = find_target_windows()
                if not fresh:
                    print(f"[WARN] No {TARGET_EXE} windows found.")
                    continue
                state["selected"] = prompt_selection(fresh)
                print(f"[OK] Now tracking {len(state['selected'])} window(s).")
    finally:
        user32.UnregisterHotKey(None, HOTKEY_TOGGLE)
        user32.UnregisterHotKey(None, HOTKEY_RESCAN)
        if state["view_only"]:
            print("[INFO] Restoring windows before exit...")
            apply_mode(state["selected"], False)
        print("[BYE] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
