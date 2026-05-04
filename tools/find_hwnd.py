import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetClassNameW = user32.GetClassNameW
IsWindowVisible = user32.IsWindowVisible

results = []

def enum_cb(hwnd, lparam):
    if IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(512)
        GetWindowTextW(hwnd, buf, 512)
        title = buf.value
        cls_buf = ctypes.create_unicode_buffer(256)
        GetClassNameW(hwnd, cls_buf, 256)
        cls_name = cls_buf.value
        if title:
            results.append((hwnd, title, cls_name))
    return True

user32.EnumWindows(EnumWindowsProc(enum_cb), 0)

print(f"Found {len(results)} visible windows\n")

keywords = ["洛克", "roco", "kingdom", "Tencent", "WeGame", "Dnf", "game"]
print("=== Possible game windows ===")
for hwnd, title, cls in sorted(results, key=lambda x: x[1].lower()):
    lower = title.lower()
    if any(k.lower() in lower for k in keywords):
        print(f"  hwnd={hwnd} (0x{hwnd:X})  class=\"{cls}\"  title=\"{title}\"")

print("\n=== All visible windows ===")
for hwnd, title, cls in sorted(results, key=lambda x: x[1].lower()):
    try:
        print(f"  hwnd={hwnd} (0x{hwnd:X})  class=\"{cls}\"  title=\"{title}\"")
    except UnicodeEncodeError:
        print(f"  hwnd={hwnd} (0x{hwnd:X})  class=\"{cls}\"  title=<unicode>")