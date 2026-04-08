import win32gui

def callback(hwnd, results):
    title = win32gui.GetWindowText(hwnd)
    if title and ('梦幻' in title or 'mhxy' in title.lower()):
        rect = win32gui.GetWindowRect(hwnd)
        cls = win32gui.GetClassName(hwnd)
        visible = win32gui.IsWindowVisible(hwnd)
        results.append((hwnd, title, rect, cls, visible))

results = []
win32gui.EnumWindows(callback, results)
for r in results:
    print(f'hwnd={r[0]}, title="{r[1]}", rect={r[2]}, class={r[3]}, visible={r[4]}')
