#!/usr/bin/env python3

import os
import pwd
import shutil
import stat
import sys
from pathlib import Path

SCRIPT_NAME = "htb-creds.py"
INSTALL_NAME = "htb-creds"
INSTALL_DIR = Path("/usr/local/bin")


def resolve_target_user():
    sudo_user = os.environ.get("SUDO_USER")

    if sudo_user and sudo_user != "root":
        try:
            return pwd.getpwnam(sudo_user)
        except KeyError:
            pass

    return pwd.getpwuid(os.getuid())


def main():
    source = Path(__file__).resolve().parent / SCRIPT_NAME

    if not source.exists():
        print(f"[-] Could not find {SCRIPT_NAME} next to setup.py")
        sys.exit(1)

    destination = INSTALL_DIR / INSTALL_NAME

    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        mode = destination.stat().st_mode
        destination.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except PermissionError:
        print(f"[-] Permission denied writing to {INSTALL_DIR}")
        print("    Re-run with sudo:")
        print(f"    sudo python3 {Path(__file__).name}")
        sys.exit(1)

    print(f"[+] Installed htb-creds to {destination}")

    user = resolve_target_user()
    base_dir = Path(user.pw_dir) / "htb-creds"
    configs_dir = base_dir / "configs"
    loot_dir = base_dir / "loot"

    for directory in (base_dir, configs_dir, loot_dir):
        directory.mkdir(parents=True, exist_ok=True)

        if os.getuid() == 0:
            os.chown(directory, user.pw_uid, user.pw_gid)

    print(f"[+] Created {base_dir}")
    print(f"    configs: {configs_dir}")
    print(f"    loot:    {loot_dir}")

    print("[+] Run this to configure your first engagement:")
    print("    htb-creds setup <name> [directory]")


if __name__ == "__main__":
    main()
