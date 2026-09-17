# htb-creds
Simple python script to quickly track and manage credentials found during HTB/CTF engagements. Supports multiple engagements, each with its own credential store.

## Install

```
sudo python3 setup.py
```

This copies `htb-creds.py` to `/usr/local/bin/htb-creds` (executable), making `htb-creds` available as a command. It also creates, under the invoking user's home directory (even when run with `sudo`):

```
~/htb-creds/
└── configs/   # config.json (current engagement + known engagements)
```

There's no default "loot" directory — every engagement's credential folder has to be placed explicitly (see `setup` below).

## Usage

```
htb-creds setup <name> <parent_dir>  # register and switch to an engagement
                                      # parent_dir must be an absolute path; a subdirectory
                                      # named after <name> is created inside it, e.g.
                                      # htb-creds setup fluffy /home/kali/HTB-boxes/creds
                                      #   -> /home/kali/HTB-boxes/creds/fluffy/htb_creds.json
htb-creds use <name>                 # switch to a previously configured engagement
htb-creds import <file> [options]    # import a raw creds JSON file as a (new or existing) engagement
htb-creds --engagements              # list configured engagements
htb-creds --current                  # show the currently selected engagement

htb-creds -a host="10.10.11.5" svc="ssh" user="robert" pass="<password>"
htb-creds -l
htb-creds -e 2 pass="<new-password>"
htb-creds -r 2
htb-creds --options
```

Run `htb-creds -h` for the full flag reference, or `htb-creds <command> -h` (e.g. `htb-creds import -h`, `htb-creds setup -h`) for a command's own options.

Credentials for the current engagement are stored as `htb_creds.json` inside that engagement's directory.

Each `htb_creds.json` is tagged with the engagement it belongs to:

```json
{
    "engagement": "fluffy",
    "credentials": [
        {
            "host": "",
            "service": "",
            "domain": "",
            "username": "<username>",
            "password": "<password>",
            "hash": "",
            "notes": ""
        }
    ]
}
```

Older files stored as a bare list are still read fine, and get upgraded to the tagged format the next time a credential is added, edited, or removed.

### Importing a raw JSON file

`use <name>` only switches between engagements you've already registered — it doesn't know what to do with an arbitrary file. To pull in credentials you (or another tool) already dumped to a JSON file, use `import` instead:

```
htb-creds import ~/HTB-boxes/creds/fluffy/htb_creds.json
```

The file can be either a bare list of credential objects, or a tagged object like the one above. `import` will:

- Register the file's directory as an engagement, choosing the name from (in order): `--engagement`/`-n`, the file's own `"engagement"` field, or the file's parent directory name (`fluffy`, above).
- Merge the file's credentials into that engagement's `htb_creds.json`, skipping exact duplicates — safe to re-run on the same file.
- Switch to the newly imported engagement (pass `--no-switch` to import without changing your current engagement).

Options (see `htb-creds import -h` for the full text):

```
htb-creds import <file> -n <engagement>    # override the inferred engagement name
htb-creds import <file> -d <parent_dir>    # manage the engagement under a different (absolute) parent dir;
                                            # same rule as 'setup' - a subdirectory named after the
                                            # engagement is created inside it
htb-creds import <file> --no-switch        # import without switching the current engagement
```

##DISCLAIMER: 
This project is mainly vibecoded. However, if it works, it works, and it's free. The project simply seeks to enable quick credential management when working on Hack The Box, TryHackMe, general CTFs, or maybe even more daunting things like OSCP. 

I put this together since I was tired of manually moving credentials back and forth between my Kali VM and note-taking platforms like Joplin.