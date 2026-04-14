from __future__ import annotations

import argparse
import os
import sys
import time

import sys_util

def _default_out_path() -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    return os.path.abspath(f"assets/mhxy_{ts}.png")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="梦幻西游 ONLINE")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    sys_util.set_dpi_aware()

    hwnd = sys_util.find_window_by_title_substring(args.title)
    if not hwnd:
        print(f"未找到窗口：标题包含 {args.title!r}", file=sys.stderr)
        return 2

    sys_util.activate_window(hwnd)
    width, height, bgra = sys_util.capture_bgra(hwnd)

    out = args.out.strip()
    if not out:
        out_path = _default_out_path()
    else:
        out_path = os.path.abspath(out)
        if os.path.isdir(out_path):
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(out_path, f"mhxy_{ts}.png")

    sys_util.save_png_32bgra(out_path, width, height, bgra)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
