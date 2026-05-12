import argparse
import os

import sys_util
from mhxy_auth import MhxyAuth


def main() -> None:
    sys_util.load_dotenv()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    ap_login = sub.add_parser("login")
    ap_login.add_argument("--server", type=str, default=os.getenv("MHXY_SERVER_NAME", "乘风破浪"))
    ap_login.add_argument("--debug", action="store_true")

    ap_logout = sub.add_parser("logout")
    ap_logout.add_argument("--debug", action="store_true")

    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help()
        return
    if getattr(args, "debug", False):
        os.environ["DEBUG"] = "1"

    auth = MhxyAuth()
    if args.cmd == "login":
        r = auth.ensure_logged_in(server_name=str(args.server))
        print(r.get("ok"), r.get("reason"))
        return
    if args.cmd == "logout":
        r = auth.ensure_logged_out()
        print(r.get("ok"), r.get("reason"))
        return


if __name__ == "__main__":
    main()
