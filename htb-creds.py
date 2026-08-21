#!/usr/bin/env python3

import argparse
import json
import os
import pwd
import shutil
import sys
from pathlib import Path

BASE_DIR = Path.home() / "htb-creds"
CONFIG_DIR = BASE_DIR / "configs"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOOT_DIR = BASE_DIR / "loot"
CREDS_FILENAME = "htb_creds.json"
INSTALLED_BINARY = Path("/usr/local/bin/htb-creds")

FIELDS = [
    "host",
    "service",
    "domain",
    "username",
    "password",
    "hash",
    "notes",
]

ALIASES = {
    "host": "host",
    "service": "service",
    "svc": "service",
    "domain": "domain",
    "username": "username",
    "user": "username",
    "password": "password",
    "pass": "password",
    "hash": "hash",
    "notes": "notes",
    "note": "notes",
}


def load_config():
    if not CONFIG_FILE.exists():
        return {"current": None, "engagements": {}}

    try:
        with CONFIG_FILE.open() as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"[-] Unable to read config: {CONFIG_FILE}")
        sys.exit(1)

    return config


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=4)


def setup(name, directory=None):
    engagement = name.strip()

    if not engagement:
        print("[-] Engagement name cannot be empty.")
        sys.exit(1)

    if directory:
        box_dir = Path(directory).expanduser().resolve()

        if not box_dir.exists():
            print(f"[-] Directory does not exist: {box_dir}")
            sys.exit(1)

        if not box_dir.is_dir():
            print(f"[-] Not a directory: {box_dir}")
            sys.exit(1)
    else:
        box_dir = LOOT_DIR / engagement
        box_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    config["engagements"][engagement] = str(box_dir)
    config["current"] = engagement
    save_config(config)

    creds_file = box_dir / CREDS_FILENAME

    if not creds_file.exists():
        with creds_file.open("w") as f:
            json.dump([], f, indent=4)

    print(f"[+] Engagement '{engagement}' set to:")
    print(f"    {box_dir}")
    print("[+] Credential file:")
    print(f"    {creds_file}")
    print(f"[+] Current engagement: {engagement}")


def use_engagement(name):
    config = load_config()

    if name not in config["engagements"]:
        print(f"[-] Unknown engagement: {name}")
        print("    Run 'htb-creds --engagements' to see configured engagements.")
        sys.exit(1)

    config["current"] = name
    save_config(config)

    print(f"[+] Switched to engagement: {name}")
    print(f"    {config['engagements'][name]}")


def list_engagements():
    config = load_config()

    if not config["engagements"]:
        print("[*] No engagements configured.")
        print("    Run:")
        print("    htb-creds setup <name> [directory]")
        return

    print("Configured engagements:\n")

    for engagement, directory in config["engagements"].items():
        marker = "*" if engagement == config["current"] else " "
        print(f"  {marker} {engagement:<20} {directory}")


def get_creds_file():
    config = load_config()
    current = config.get("current")

    if not current:
        print("[-] No engagement selected.")
        print("    Run:")
        print("    htb-creds setup <name> [directory]")
        sys.exit(1)

    directory = config["engagements"].get(current)

    if not directory:
        print(f"[-] Current engagement '{current}' is not configured.")
        sys.exit(1)

    box_dir = Path(directory)

    if not box_dir.exists():
        print("[-] Configured directory no longer exists:")
        print(f"    {box_dir}")
        sys.exit(1)

    return box_dir / CREDS_FILENAME


def load_creds():
    creds_file = get_creds_file()

    if not creds_file.exists():
        return []

    try:
        with creds_file.open() as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"[-] Invalid JSON in {creds_file}")
        sys.exit(1)

    if not isinstance(data, list):
        print(f"[-] Invalid credential file format: {creds_file}")
        sys.exit(1)

    return data


def save_creds(creds):
    creds_file = get_creds_file()

    with creds_file.open("w") as f:
        json.dump(creds, f, indent=4)


def parse_fields(arguments):
    values = {}

    for item in arguments:
        if "=" not in item:
            print(f"[-] Invalid argument: {item}")
            print('    Expected format: key="value"')
            sys.exit(1)

        key, value = item.split("=", 1)
        key = key.lower().strip()

        if key not in ALIASES:
            print(f"[-] Unknown field: {key}")
            print("    Run 'htb-creds --options' to see valid fields.")
            sys.exit(1)

        values[ALIASES[key]] = value

    return values


def print_credential(credential):
    for field in FIELDS:
        value = credential.get(field, "")

        if value:
            print(f"    {field:<10} {value}")


def add_credential(arguments):
    credential = {field: "" for field in FIELDS}

    values = parse_fields(arguments)
    credential.update(values)

    creds = load_creds()
    creds.append(credential)
    save_creds(creds)

    print(f"[+] Credential added as [{len(creds)}]:")
    print_credential(credential)


def edit_credential(arguments):
    if len(arguments) < 2:
        print("[-] Edit requires an ID and at least one key=value pair.")
        print('    Example: htb-creds -e 2 user="robert" service="ssh"')
        sys.exit(1)

    try:
        index = int(arguments[0])
    except ValueError:
        print(f"[-] Invalid credential ID: {arguments[0]}")
        sys.exit(1)

    creds = load_creds()

    if not creds:
        print("[-] No credentials stored.")
        sys.exit(1)

    if index < 1 or index > len(creds):
        print(f"[-] Invalid credential ID: {index}")
        print(f"    Valid range: 1-{len(creds)}")
        sys.exit(1)

    values = parse_fields(arguments[1:])

    credential = creds[index - 1]

    # Ensure older/incomplete entries still contain every expected key
    for field in FIELDS:
        credential.setdefault(field, "")

    credential.update(values)

    save_creds(creds)

    print(f"[+] Credential [{index}] updated:")
    print_credential(credential)


def list_credentials():
    creds = load_creds()

    if not creds:
        print("[*] No credentials stored.")
        return

    for index, cred in enumerate(creds, start=1):
        print(f"\n[{index}]")
        print_credential(cred)


def remove_credential(index):
    creds = load_creds()

    if not creds:
        print("[-] No credentials stored.")
        sys.exit(1)

    if index < 1 or index > len(creds):
        print(f"[-] Invalid credential ID: {index}")
        print(f"    Valid range: 1-{len(creds)}")
        sys.exit(1)

    removed = creds.pop(index - 1)
    save_creds(creds)

    print(f"[+] Removed credential [{index}]:")
    print_credential(removed)


def show_options():
    print("Available credential fields:\n")

    print("    host")
    print("    service     alias: svc")
    print("    domain")
    print("    username    alias: user")
    print("    password    alias: pass")
    print("    hash")
    print("    notes       alias: note")

    print("\nAdd example:")
    print(
        '    htb-creds -a host="10.10.11.5" '
        'svc="ssh" user="robert" pass="Password123"'
    )

    print("\nEdit example:")
    print(
        '    htb-creds -e 2 '
        'svc="ssh" notes="Also valid for SSH"'
    )


def show_current():
    config = load_config()
    current = config.get("current")

    if not current:
        print("[-] No engagement selected.")
        print("    Run:")
        print("    htb-creds setup <name> [directory]")
        sys.exit(1)

    creds_file = get_creds_file()
    print(f"Current engagement: {current}")
    print(f"Credential file: {creds_file}")


def resolve_target_user():
    sudo_user = os.environ.get("SUDO_USER")

    if sudo_user and sudo_user != "root":
        try:
            return pwd.getpwnam(sudo_user)
        except KeyError:
            pass

    return pwd.getpwuid(os.getuid())


def uninstall():
    if os.geteuid() != 0:
        print("[-] Uninstalling requires root privileges.")
        print("    Re-run with sudo:")
        print("    sudo htb-creds --uninstall")
        sys.exit(1)

    user = resolve_target_user()
    base_dir = Path(user.pw_dir) / "htb-creds"

    print("[!] This will permanently delete:")
    print(f"    {base_dir} (all engagements and stored credentials)")
    print(f"    {INSTALLED_BINARY}")

    answer = input("Uninstall htb-creds? [y/N] ").strip().lower()

    if answer != "y":
        print("[*] Uninstall cancelled.")
        return

    if base_dir.exists():
        shutil.rmtree(base_dir)
        print(f"[+] Removed {base_dir}")

    if INSTALLED_BINARY.exists():
        INSTALLED_BINARY.unlink()
        print(f"[+] Removed {INSTALLED_BINARY}")

    print("[+] htb-creds has been uninstalled.")


def main():
    parser = argparse.ArgumentParser(
        description="Simple HTB credential manager"
    )

    parser.add_argument(
        "-a",
        "--add",
        nargs="+",
        metavar="KEY=VALUE",
        help="Add a credential",
    )

    parser.add_argument(
        "-e",
        "--edit",
        nargs="+",
        metavar=("ID", "KEY=VALUE"),
        help="Edit an existing credential by ID",
    )

    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List stored credentials",
    )

    parser.add_argument(
        "-r",
        "--remove",
        type=int,
        metavar="ID",
        help="Remove a credential by ID",
    )

    parser.add_argument(
        "--options",
        action="store_true",
        help="Show available credential fields",
    )

    parser.add_argument(
        "--current",
        action="store_true",
        help="Show the currently selected engagement",
    )

    parser.add_argument(
        "--engagements",
        action="store_true",
        help="List all configured engagements",
    )

    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove htb-creds and all stored engagements/credentials",
    )

    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser(
        "setup",
        help="Register an engagement and select it",
    )

    setup_parser.add_argument(
        "name",
        help="Name for this engagement",
    )

    setup_parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help=(
            "Directory in which htb_creds.json will be stored "
            f"(defaults to a new directory under {LOOT_DIR})"
        ),
    )

    use_parser = subparsers.add_parser(
        "use",
        help="Switch to a previously configured engagement",
    )

    use_parser.add_argument(
        "name",
        help="Name of the engagement to switch to",
    )

    args = parser.parse_args()

    if args.uninstall:
        uninstall()

    elif args.command == "setup":
        setup(args.name, args.directory)

    elif args.command == "use":
        use_engagement(args.name)

    elif args.add:
        add_credential(args.add)

    elif args.edit:
        edit_credential(args.edit)

    elif args.list:
        list_credentials()

    elif args.remove is not None:
        remove_credential(args.remove)

    elif args.options:
        show_options()

    elif args.current:
        show_current()

    elif args.engagements:
        list_engagements()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()