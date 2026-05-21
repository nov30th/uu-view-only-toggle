"""
UU Remote View-Only Toggle — CustomTkinter GUI

Auto-discovers GameViewer.exe windows, no manual selection needed.
Hotkeys: Ctrl+Alt+V (toggle), Ctrl+Alt+B (rescan).
Exit via window close or tray — always restores control mode.
"""

import ctypes
import sys
import threading
from ctypes import wintypes

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Win32 API setup
# ---------------------------------------------------------------------------
TARGET_EXE = "GameViewer.exe"

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumWindowsProc, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
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


def apply_mode(selected: list[int], view_only: bool) -> list[int]:
    alive = [h for h in selected if user32.IsWindow(h)]
    enable = wintypes.BOOL(not view_only)
    for top in alive:
        for child in collect_descendants(top):
            user32.EnableWindow(child, enable)
    return alive


# ---------------------------------------------------------------------------
# Hotkey thread (runs Win32 message loop for global hotkeys)
# ---------------------------------------------------------------------------
class HotkeyWatcher(threading.Thread):
    """Background thread that registers Ctrl+Alt+V / Ctrl+Alt+B and calls back."""

    def __init__(self, on_toggle, on_rescan):
        super().__init__(daemon=True)
        self.on_toggle = on_toggle
        self.on_rescan = on_rescan
        self._quit = threading.Event()

    def run(self):
        hwnd = None
        try:
            user32.RegisterHotKey(hwnd, HOTKEY_TOGGLE, MOD_CONTROL | MOD_ALT, VK_V)
            user32.RegisterHotKey(hwnd, HOTKEY_RESCAN, MOD_CONTROL | MOD_ALT, VK_B)
        except Exception:
            pass

        msg = wintypes.MSG()
        while not self._quit.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), hwnd, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == WM_HOTKEY:
                if msg.wParam == HOTKEY_TOGGLE:
                    self.on_toggle()
                elif msg.wParam == HOTKEY_RESCAN:
                    self.on_rescan()

    def stop(self):
        self._quit.set()
        user32.UnregisterHotKey(None, HOTKEY_TOGGLE)
        user32.UnregisterHotKey(None, HOTKEY_RESCAN)
        user32.PostQuitMessage(0)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class UUViewOnlyApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        super().__init__()

        self.title("UU 仅观看模式")
        self.geometry("280x190")
        self.resizable(False, False)
        self.after(200, lambda: self._bring_to_front())

        self.view_only = False
        self.selected: list[int] = []
        self.hotkey_watcher = None

        # -- Status line: icon + text --
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(pady=(8, 2))

        self.status_icon = ctk.CTkLabel(
            status_frame, text="●", font=("Segoe UI", 28), text_color="#4ade80"
        )
        self.status_icon.pack(side="left", padx=(15, 6))

        self.status_text = ctk.CTkLabel(
            status_frame, text="已找到 UU 远程窗口", font=("Microsoft YaHei UI", 13)
        )
        self.status_text.pack(side="left")

        self.hint_text = ctk.CTkLabel(
            self, text="Ctrl+Alt+V 切换", font=("Microsoft YaHei UI", 10),
            text_color="gray"
        )
        self.hint_text.pack()

        # -- Action button --
        self.action_btn = ctk.CTkButton(
            self, text="启用仅观看", font=("Microsoft YaHei UI", 14),
            height=38, corner_radius=10, fg_color="#3b82f6", hover_color="#2563eb",
            command=self.toggle_mode
        )
        self.action_btn.pack(pady=(8, 5))

        # -- Rescan button --
        self.rescan_btn = ctk.CTkButton(
            self, text="重新扫描", font=("Microsoft YaHei UI", 11),
            height=28, width=80, corner_radius=8,
            fg_color="transparent", border_width=1, border_color="#555",
            hover_color="#333", command=self.rescan_windows
        )
        self.rescan_btn.pack()

        # -- Footer --
        self.footer = ctk.CTkLabel(
            self, text="关闭自动恢复控制", font=("Microsoft YaHei UI", 9),
            text_color="gray"
        )
        self.footer.pack(pady=(6, 0))

        # Initial scan
        self.after(100, self._initial_scan)

    # -- State updates (called from hotkey thread via after()) --
    def _set_status(self, view_only: bool):
        if view_only:
            self.status_icon.configure(text_color="#f87171")
            self.status_text.configure(text="仅观看模式中")
            self.action_btn.configure(
                text="恢复控制", fg_color="#ef4444", hover_color="#dc2626"
            )
        else:
            self.status_icon.configure(text_color="#4ade80")
            self.status_text.configure(text="已找到 UU 远程窗口")
            self.action_btn.configure(
                text="启用仅观看", fg_color="#3b82f6", hover_color="#2563eb"
            )

    def _scan_success(self, windows: list[int]):
        self.selected = windows
        self.status_text.configure(text=f"已找到 {len(windows)} 个窗口")
        self.status_icon.configure(text_color="#4ade80")

    def _scan_fail(self):
        self.selected = []
        self.status_text.configure(text="未找到 UU 远程窗口")
        self.status_icon.configure(text_color="#fbbf24")

    def _bring_to_front(self):
        """Flash topmost to bring window to foreground, then release."""
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))

    # -- Core actions --
    def toggle_mode(self):
        if not self.selected:
            self._scan_fail()
            return
        self.view_only = not self.view_only
        self.selected = apply_mode(self.selected, self.view_only)
        self._set_status(self.view_only)

    def _on_hotkey_toggle(self):
        self.after(0, self.toggle_mode)

    def rescan_windows(self):
        if self.view_only:
            apply_mode(self.selected, False)
            self.view_only = False
            self._set_status(False)

        windows = find_target_windows()
        if windows:
            self.selected = windows
            self._scan_success(windows)
        else:
            self._scan_fail()

    def _on_hotkey_rescan(self):
        self.after(0, self.rescan_windows)

    def _initial_scan(self):
        windows = find_target_windows()
        if windows:
            self.selected = windows
            self._scan_success(windows)
        else:
            self._scan_fail()

        # Start hotkey watcher
        self.hotkey_watcher = HotkeyWatcher(
            on_toggle=self._on_hotkey_toggle,
            on_rescan=self._on_hotkey_rescan,
        )
        self.hotkey_watcher.start()

    def _on_close(self):
        if self.view_only:
            apply_mode(self.selected, False)
        if self.hotkey_watcher:
            self.hotkey_watcher.stop()
        self.destroy()

    def protocol(self, *args):
        if args[0] == "WM_DELETE_WINDOW":
            return super().protocol("WM_DELETE_WINDOW", lambda: self._on_close())
        return super().protocol(*args)


def main():
    app = UUViewOnlyApp()
    app.mainloop()


if __name__ == "__main__":
    main()
