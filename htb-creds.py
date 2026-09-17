#!/usr/bin/env python3

import argparse
import json
import os
import pwd
import shutil
import sys
from pathlib import Path

VERSION = "0.9"

BASE_DIR = Path.home() / "htb-creds"
CONFIG_DIR = BASE_DIR / "configs"
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDS_SUFFIX = "_htb_creds.json"
INSTALLED_BINARY = Path("/usr/local/bin/htb-creds")


def creds_filename(engagement):
    return f"{engagement}{CREDS_SUFFIX}"


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


def resolve_engagement_dir(engagement, parent_dir):
    """Resolve the per-engagement credentials folder from a REQUIRED,
    absolute parent directory. The folder itself is always named after
    the engagement and is created under that parent if it doesn't
    already exist."""
    parent = Path(parent_dir).expanduser()

    if not parent.is_absolute():
        print(f"[-] Parent directory must be an absolute path: {parent_dir}")
        sys.exit(1)

    if not parent.exists():
        print(f"[-] Parent directory does not exist: {parent}")
        sys.exit(1)

    if not parent.is_dir():
        print(f"[-] Not a directory: {parent}")
        sys.exit(1)

    box_dir = parent / engagement
    box_dir.mkdir(parents=True, exist_ok=True)

    return box_dir


def resolve_setup_dir(engagement, parent_dir=None):
    """Resolve the per-engagement credentials folder as
    <parent_dir>/<engagement>/creds, creating any missing directories
    along the way. parent_dir defaults to the user's home directory."""
    parent = Path(parent_dir).expanduser() if parent_dir else Path.home()

    if not parent.is_absolute():
        print(f"[-] Parent directory must be an absolute path: {parent_dir}")
        sys.exit(1)

    box_dir = parent / engagement / "creds"
    box_dir.mkdir(parents=True, exist_ok=True)

    return box_dir


def setup(name, parent_dir=None):
    engagement = name.strip()

    if not engagement:
        print("[-] Engagement name cannot be empty.")
        sys.exit(1)

    box_dir = resolve_setup_dir(engagement, parent_dir)

    config = load_config()
    config["engagements"][engagement] = str(box_dir)
    config["current"] = engagement
    save_config(config)

    creds_file = box_dir / creds_filename(engagement)

    if not creds_file.exists():
        with creds_file.open("w") as f:
            json.dump({"engagement": engagement, "credentials": []}, f, indent=4)

    print(f"[+] Engagement '{engagement}' set to:")
    print(f"    {box_dir}")
    print("[+] Credential file:")
    print(f"    {creds_file}")
    print(f"[+] Current engagement: {engagement}")


def use_engagement(name):
    config = load_config()

    if name not in config["engagements"]:
        print(f"[-] Unknown engagement: {name}")

        looks_like_path = os.sep in name or name.lower().endswith(".json")

        if looks_like_path or Path(name).expanduser().exists():
            print("    That looks like a file, not an engagement name.")
            print(f"    Run 'htb-creds import {name}' to import it instead.")
        else:
            print("    Run 'htb-creds --engagements' to see configured engagements.")

        sys.exit(1)

    config["current"] = name
    save_config(config)

    print(f"[+] Switched to engagement: {name}")
    print(f"    {config['engagements'][name]}")


def delete_engagement(name, keep_files=False):
    config = load_config()

    if name not in config["engagements"]:
        print(f"[-] Unknown engagement: {name}")
        print("    Run 'htb-creds --engagements' to see configured engagements.")
        sys.exit(1)

    box_dir = Path(config["engagements"][name])
    creds_file = box_dir / creds_filename(name)

    if not keep_files and creds_file.exists():
        print("[!] This will permanently delete:")
        print(f"    {creds_file}")

        answer = input(f"Delete engagement '{name}'? [y/N] ").strip().lower()

        if answer != "y":
            print("[*] Delete cancelled.")
            return

        creds_file.unlink()
        print(f"[+] Removed {creds_file}")

        try:
            box_dir.rmdir()
        except OSError:
            pass

    del config["engagements"][name]

    if config.get("current") == name:
        config["current"] = None

    save_config(config)

    print(f"[+] Engagement '{name}' removed.")

    if config.get("current") is None:
        if config["engagements"]:
            print("    Run 'htb-creds use <name>' to switch to another engagement.")
        else:
            print("    No engagements remain. Run 'htb-creds setup <name> [dir]' to create one.")


def list_engagements():
    config = load_config()

    if not config["engagements"]:
        print("[*] No engagements configured.")
        print("    Run:")
        print("    htb-creds setup <name> [dir]")
        return

    print("Configured engagements:\n")

    for engagement, directory in config["engagements"].items():
        marker = "*" if engagement == config["current"] else " "
        print(f"  {marker} {engagement:<20} {directory}")


def load_raw_json(path):
    try:
        with path.open() as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[-] Invalid JSON in {path}: {exc}")
        sys.exit(1)
    except OSError as exc:
        print(f"[-] Unable to read {path}: {exc}")
        sys.exit(1)


def extract_credentials(data, source):
    """Pull an (engagement_hint, credentials_list) pair out of an arbitrary
    creds JSON payload: either a bare list (legacy format) or a tagged
    {"engagement": ..., "credentials": [...]} object."""
    if isinstance(data, list):
        return None, data

    if isinstance(data, dict) and isinstance(data.get("credentials"), list):
        return data.get("engagement"), data["credentials"]

    print(f"[-] Unrecognized credential file format: {source}")
    sys.exit(1)


def normalize_credential(entry, source):
    if not isinstance(entry, dict):
        print(f"[-] Skipping non-object credential entry in {source}: {entry!r}")
        return None

    credential = {field: "" for field in FIELDS}

    for key, value in entry.items():
        field = ALIASES.get(str(key).lower().strip())

        if field:
            credential[field] = value

    return credential


def import_credentials(path_str, engagement_name=None, directory=None, switch=True):
    source = Path(path_str).expanduser().resolve()

    if not source.exists():
        print(f"[-] File does not exist: {source}")
        sys.exit(1)

    if not source.is_file():
        print(f"[-] Not a file: {source}")
        sys.exit(1)

    data = load_raw_json(source)
    hint, incoming = extract_credentials(data, source)

    engagement = (engagement_name or hint or source.parent.name).strip()

    if not engagement:
        print("[-] Could not determine an engagement name for this import.")
        print("    Specify one with: htb-creds import <file> --engagement <name>")
        sys.exit(1)

    config = load_config()

    if directory:
        # -d/--directory is the (required-absolute) PARENT dir - the
        # engagement's own folder is created inside it
        box_dir = resolve_engagement_dir(engagement, directory)
    elif engagement in config["engagements"]:
        # Already-known engagement: keep merging into its configured directory
        box_dir = Path(config["engagements"][engagement])
    else:
        # New engagement: manage the file where it already lives instead of
        # requiring a separate parent directory
        box_dir = source.parent
        box_dir.mkdir(parents=True, exist_ok=True)

    config["engagements"][engagement] = str(box_dir)

    if switch:
        config["current"] = engagement

    save_config(config)

    creds_file = box_dir / creds_filename(engagement)
    existing = []

    if creds_file.exists() and creds_file != source:
        existing_data = load_raw_json(creds_file)
        _, existing = extract_credentials(existing_data, creds_file)

    imported = 0

    for entry in incoming:
        credential = normalize_credential(entry, source)

        if credential is None:
            continue

        if credential not in existing:
            existing.append(credential)

        imported += 1

    with creds_file.open("w") as f:
        json.dump({"engagement": engagement, "credentials": existing}, f, indent=4)

    print(f"[+] Imported {imported} credential(s) from {source}")
    print(f"[+] Engagement '{engagement}' -> {box_dir}")
    print(f"[+] Credential file: {creds_file}")

    if switch:
        print(f"[+] Current engagement: {engagement}")


def get_creds_file():
    config = load_config()
    current = config.get("current")

    if not current:
        print("[-] No engagement selected.")
        print("    Run:")
        print("    htb-creds setup <name> [dir]")
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

    return box_dir / creds_filename(current)


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

    # Legacy files stored a bare list, with no record of which engagement
    # they belonged to. New files are tagged: {"engagement": ..., "credentials": [...]}
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("credentials"), list):
        return data["credentials"]

    print(f"[-] Invalid credential file format: {creds_file}")
    sys.exit(1)


def save_creds(creds):
    creds_file = get_creds_file()
    config = load_config()
    engagement = config.get("current")

    payload = {"engagement": engagement, "credentials": creds}

    with creds_file.open("w") as f:
        json.dump(payload, f, indent=4)


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
    config = load_config()
    creds = load_creds()

    print(f"Current engagement: {config.get('current')}")

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
        print("    htb-creds setup <name> [dir]")
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
    config_file = base_dir / "configs" / "config.json"

    engagements = {}

    if config_file.exists():
        try:
            with config_file.open() as f:
                engagements = json.load(f).get("engagements", {})
        except (json.JSONDecodeError, OSError):
            pass

    print("[!] This will permanently delete:")
    print(f"    {base_dir} (engagement configuration)")
    print(f"    {INSTALLED_BINARY}")

    if engagements:
        print("    Credential files for these engagements:")

        for engagement, directory in engagements.items():
            print(f"      {Path(directory) / creds_filename(engagement)}")
    else:
        print("    (no registered engagements found; any credential files")
        print("     outside a registered engagement's directory are left alone)")

    answer = input("Uninstall htb-creds? [y/N] ").strip().lower()

    if answer != "y":
        print("[*] Uninstall cancelled.")
        return

    for engagement, directory in engagements.items():
        box_dir = Path(directory)
        creds_file = box_dir / creds_filename(engagement)

        if creds_file.exists():
            creds_file.unlink()
            print(f"[+] Removed {creds_file}")

            try:
                box_dir.rmdir()
            except OSError:
                pass

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
        "--version",
        action="version",
        version=f"htb-creds v{VERSION}",
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
        "dir",
        metavar="dir",
        nargs="?",
        default=None,
        help=(
            "Absolute path to the parent directory under which this "
            "engagement's folder is created (e.g. /home/kali/HTB-boxes). "
            "A subdirectory <dir>/<name>/creds is created if it doesn't "
            "already exist, and <name>_htb_creds.json is stored there. "
            "Defaults to your home directory."
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

    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete a configured engagement",
    )

    delete_parser.add_argument(
        "name",
        help="Name of the engagement to delete",
    )

    delete_parser.add_argument(
        "--keep-files",
        action="store_true",
        help=(
            "Only remove the engagement from configuration; leave its "
            "credential file on disk"
        ),
    )

    import_parser = subparsers.add_parser(
        "import",
        help="Import credentials from a raw JSON file",
    )

    import_parser.add_argument(
        "file",
        help=(
            "Path to a JSON credentials file: either a bare list of "
            "credential objects, or an object with an 'engagement' name "
            "and a 'credentials' list"
        ),
    )

    import_parser.add_argument(
        "-n",
        "--engagement",
        default=None,
        help=(
            "Engagement name to import into (defaults to the file's "
            "'engagement' field, then its parent directory's name)"
        ),
    )

    import_parser.add_argument(
        "-d",
        "--directory",
        metavar="parent_dir",
        default=None,
        help=(
            "Absolute path to a parent directory to manage this "
            "engagement's credentials under (a subdirectory named after "
            "the engagement is created inside it). Defaults to the "
            "imported file's own directory for a new engagement, or an "
            "existing engagement's configured directory"
        ),
    )

    import_parser.add_argument(
        "--no-switch",
        action="store_true",
        help="Import without switching the current engagement",
    )

    args = parser.parse_args()

    if args.uninstall:
        uninstall()

    elif args.command == "setup":
        setup(args.name, args.dir)

    elif args.command == "use":
        use_engagement(args.name)

    elif args.command == "delete":
        delete_engagement(args.name, keep_files=args.keep_files)

    elif args.command == "import":
        import_credentials(
            args.file,
            engagement_name=args.engagement,
            directory=args.directory,
            switch=not args.no_switch,
        )

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