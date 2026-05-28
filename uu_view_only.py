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
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
LWA_ALPHA = 0x00000002
SW_SHOW = 5
SW_HIDE = 0
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

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


def print_window_list(windows: list[int]) -> None:
    for i, hwnd in enumerate(windows, 1):
        title = get_window_title(hwnd) or "(no title)"
        cls = get_window_class(hwnd)
        w, h = get_window_size(hwnd)
        print(f"  [{i}] HWND=0x{hwnd:08X}  size={w}x{h}  class={cls}")
        print(f"      title: {title}")


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
    print(f"[DEBUG] find_target_windows: found {len(matches)} window(s) for {TARGET_EXE}")
    if matches:
        print_window_list(matches)
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
    dead = len(selected) - len(alive)
    if dead:
        print(f"[WARN] {dead} target window(s) no longer exist. Press Ctrl+Alt+B to rescan.")
    enable = wintypes.BOOL(not view_only)
    affected = 0
    mode = "VIEW-ONLY (input blocked)" if view_only else "CONTROL (normal)"
    print(f"[DEBUG] apply_mode: {mode}")
    for top in alive:
        title = get_window_title(top) or "(no title)"
        cls = get_window_class(top)
        children = collect_descendants(top)
        print(f"  Top HWND=0x{top:08X} class={cls} title={title}  children={len(children)}")
        for child in children:
            user32.EnableWindow(child, enable)
            affected += 1
    print(f"[OK] Mode: {mode}  | top windows: {len(alive)}  | children affected: {affected}")
    return alive


# ---------------------------------------------------------------------------
# Invisible overlay window -- physically blocks mouse clicks on UU window
# ---------------------------------------------------------------------------
def create_overlay(target_hwnd: int) -> int:
    """Create a transparent topmost overlay covering *target_hwnd*.
    The overlay captures all mouse input, preventing clicks from reaching
    the UU remote window underneath."""
    overlay_hwnd = user32.CreateWindowExW(
        WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOPMOST,
        "Static",
        None,
        WS_POPUP | WS_VISIBLE,
        0, 0, 1, 1,
        None,
        None,
        None,
        None,
    )
    if overlay_hwnd:
        user32.SetLayeredWindowAttributes(overlay_hwnd, 0, 1, LWA_ALPHA)
    return overlay_hwnd


def position_overlay(overlay_hwnd: int, target_hwnd: int) -> None:
    """Move and resize *overlay_hwnd* to exactly cover *target_hwnd*."""
    r = wintypes.RECT()
    if user32.GetWindowRect(target_hwnd, ctypes.byref(r)):
        w, h = r.right - r.left, r.bottom - r.top
        user32.SetWindowPos(
            overlay_hwnd, HWND_TOPMOST,
            r.left, r.top, w, h,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )


def destroy_overlay(overlay_hwnd: int) -> None:
    if overlay_hwnd and user32.IsWindow(overlay_hwnd):
        user32.DestroyWindow(overlay_hwnd)


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
        ok_toggle = user32.RegisterHotKey(hwnd, HOTKEY_TOGGLE, MOD_CONTROL | MOD_ALT, VK_V)
        ok_rescan = user32.RegisterHotKey(hwnd, HOTKEY_RESCAN, MOD_CONTROL | MOD_ALT, VK_B)
        if not ok_toggle:
            print(f"[ERR] Register Ctrl+Alt+V failed (error {ctypes.get_last_error()})")
        if not ok_rescan:
            print(f"[WARN] Register Ctrl+Alt+B failed (error {ctypes.get_last_error()})")
        if ok_toggle and ok_rescan:
            print("[OK] Hotkeys registered: Ctrl+Alt+V (toggle), Ctrl+Alt+B (rescan)")

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
        self.overlays: dict[int, int] = {}  # target_hwnd -> overlay_hwnd
        self.overlay_last_rects: dict[int, tuple] = {}  # hwnd -> (x, y, w, h)
        self._overlay_poll_id: str | None = None

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
        print(f"[OK] Tracking {len(windows)} window(s):")
        for hwnd in windows:
            title = get_window_title(hwnd) or "(no title)"
            cls = get_window_class(hwnd)
            w, h = get_window_size(hwnd)
            print(f"  HWND=0x{hwnd:08X}  size={w}x{h}  class={cls}  title={title}")

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
            print("[WARN] No windows selected, cannot toggle")
            self._scan_fail()
            return
        self.view_only = not self.view_only
        print(f"[INFO] Toggling to view_only={self.view_only}")
        self.selected = apply_mode(self.selected, self.view_only)
        if self.view_only:
            self._create_overlays()
            self._start_overlay_poller()
        else:
            self._destroy_all_overlays()
            self._stop_overlay_poller()
        self._set_status(self.view_only)

    def _create_overlays(self):
        """Create invisible overlay windows for each tracked UU window."""
        self._destroy_all_overlays()
        for hwnd in self.selected:
            if user32.IsWindow(hwnd):
                overlay = create_overlay(hwnd)
                if overlay:
                    position_overlay(overlay, hwnd)
                    self.overlays[hwnd] = overlay
                    # Record initial rect so _update_overlays can diff
                    r = wintypes.RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                        self.overlay_last_rects[hwnd] = (r.left, r.top, r.right - r.left, r.bottom - r.top)
                    print(f"[OK] Overlay created for HWND=0x{hwnd:08X} (overlay=0x{overlay:08X})")

    def _destroy_all_overlays(self):
        for hwnd, overlay in list(self.overlays.items()):
            destroy_overlay(overlay)
        self.overlays.clear()
        self.overlay_last_rects.clear()

    def _start_overlay_poller(self):
        if self._overlay_poll_id is not None:
            self.after_cancel(self._overlay_poll_id)
        self._update_overlays()

    def _stop_overlay_poller(self):
        if self._overlay_poll_id is not None:
            self.after_cancel(self._overlay_poll_id)
            self._overlay_poll_id = None

    def _update_overlays(self):
        """Re-position overlays only when UU windows actually move or resize."""
        if not self.view_only:
            self._overlay_poll_id = None
            return
        dead = []
        for hwnd, overlay in list(self.overlays.items()):
            if not user32.IsWindow(hwnd):
                dead.append(hwnd)
                destroy_overlay(overlay)
                continue
            if user32.IsIconic(hwnd):
                user32.ShowWindow(overlay, SW_HIDE)
                continue

            new_rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(new_rect)):
                user32.ShowWindow(overlay, SW_HIDE)
                continue

            new_size = (new_rect.left, new_rect.top, new_rect.right - new_rect.left, new_rect.bottom - new_rect.top)
            old_size = self.overlay_last_rects.get(hwnd)
            if old_size != new_size:
                self.overlay_last_rects[hwnd] = new_size
                user32.SetWindowPos(
                    overlay, HWND_TOPMOST,
                    *new_size,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )
            user32.ShowWindow(overlay, SW_SHOW)

        for hwnd in dead:
            del self.overlays[hwnd]
            self.overlay_last_rects.pop(hwnd, None)

        if self.view_only:
            self._overlay_poll_id = self.after(1000, self._update_overlays)
        else:
            self._overlay_poll_id = None

    def _on_hotkey_toggle(self):
        self.after(0, self.toggle_mode)

    def rescan_windows(self):
        if self.view_only:
            apply_mode(self.selected, False)
            self._destroy_all_overlays()
            self._stop_overlay_poller()
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
        print("[INFO] Initial scan...")
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
            self._destroy_all_overlays()
            self._stop_overlay_poller()
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
