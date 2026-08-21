# htb-creds
Simple python script to quickly track and manage credentials found during HTB/CTF engagements. Supports multiple engagements, each with its own credential store.

## Install

```
sudo python3 setup.py
```

This copies `htb-creds.py` to `/usr/local/bin/htb-creds` (executable), making `htb-creds` available as a command. It also creates, under the invoking user's home directory (even when run with `sudo`):

```
~/htb-creds/
├── configs/   # config.json (current engagement + known engagements)
└── loot/      # default parent directory for engagement credential stores
```

## Usage

```
htb-creds setup <name> [directory]   # register and switch to an engagement
                                      # omit [directory] to create one under ~/htb-creds/loot/<name>
htb-creds use <name>                 # switch to a previously configured engagement
htb-creds --engagements              # list configured engagements
htb-creds --current                  # show the currently selected engagement

htb-creds -a host="10.10.11.5" svc="ssh" user="robert" pass="Password123"
htb-creds -l
htb-creds -e 2 pass="NewPassword123"
htb-creds -r 2
htb-creds --options
```

Credentials for the current engagement are stored as `htb_creds.json` inside that engagement's directory. Passing a `[directory]` to `setup` points the engagement at an existing directory outside `~/htb-creds/loot` instead.
