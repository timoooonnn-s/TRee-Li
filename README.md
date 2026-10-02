# TRee-Li: Switch Manager

```
 _____  ____                      _      _
|_   _||  _ \   ___   ___        | |    (_)
  | |  | |_) | / _ \ / _ \ _____ | |    | |
  | |  |  _ < |  __/|  __/|_____|| |___ | |
  |_|  |_| \_\ \___| \___|       |_____||_|
```

A switch manager for the terminal: search your switch list, ssh into a switch,
log out, and you're back in the list. It runs on any Linux server you
reach over SSH (PuTTY, Tabby, ...). No GUI and no X11.

Inspired by [V-Li: Switch Manager](https://github.com/seismicindustries/switch-manager).
TRee-Li keeps its menu and keys, but runs ssh *inside* your terminal instead of
opening a new desktop window.

- **One file, Python 3 standard library only.** No pip, no venv, no root.
- **Credentials asked once per session.** They stay in memory only and are forgotten when TRee-Li exits.
- **After you log out of a switch, you're back in TRee-Li.**

## Screen

```
  TRee-Li  Switch Manager                                     timmy · 2/29 switches
───────────────────────────────────────────────────────────────────────────────────

   ssh   ping   traceroute   batch ping   details   help   exit

  ›  ber core

   NAME          IP            SUBNET    ALIAS                COMMENT    PING ▲
   ─────────────────────────────────────────────────────────────────────────────
 ▌ ber-core-01   192.0.2.1     ber       Core switch Berlin   5520       ● down
   ber-core-02   192.0.2.7     ber       Core switch Berlin   VSP7400    ● up

───────────────────────────────────────────────────────────────────────────────────
  Enter run  ←→ command  type search  F1-F6 sort  ^R reload  ^C quit
```

Colours are shades of blue. They adapt to the terminal: 256 colours in Tabby or with
`TERM=xterm-256color`, 8 colours in PuTTY's default `TERM=xterm`, and plain bold/reverse without colour.
Lines and symbols use Unicode on UTF-8 terminals. If they look garbled (an old PuTTY
font or a non-UTF-8 character set), start with `--ascii` or set `charset = ascii`.

## Keys

| Key | Action |
|---|---|
| `Up` `Down` `PgUp` `PgDn` `Home` `End` | select a switch |
| `Left` `Right` | select a command |
| `Enter` | run the selected command on the selected switch |
| just type | search. All words must match (`ber core` finds Berlin core switches) |
| `Backspace`, `Ctrl-U`, `ESC` | edit / clear the search (`ESC` also cancels a running batch ping) |
| `F1`...`F6`, or `Tab` / `Shift-Tab` | sort by column (press the same F-key again to reverse) |
| `Ctrl-R` | reload the switch list |
| `Ctrl-C` | quit |

In output windows (ping, traceroute, details, help): arrow keys and `PgUp`/`PgDn` scroll, and `ESC` / `Enter` / `q` closes.

## Commands

| Command | What it does |
|---|---|
| **ssh** | Connects to the switch. The first time, TRee-Li asks for your username (pre-filled with your Linux user) and password, and types the password for you from then on. Log out of the switch to come back. Use `~.` to force-close a hanging session. |
| **ping** | `ping -c 4`, with live output. Also updates the Ping column. |
| **traceroute** | Uses `traceroute`, or `tracepath` when traceroute isn't installed. |
| **batch ping** | Pings every switch in the **current (filtered) list** in parallel and fills the Ping column with UP/DOWN. Press `F6` to sort by Ping. |
| **details** | Shows every CSV field of the switch, including columns not in the table. |
| **help** | Shows keys, the current file paths and settings. |
| **exit** | Quits and forgets the credentials. |

## Install

Requirements: Linux, Python ≥ 3.8 (`python3 --version`), OpenSSH client, `ping`.
`traceroute` or `tracepath` is optional.

```bash
git clone <repo-url> ~/tree-li        # or any directory, e.g. a shared team folder
cd ~/tree-li
cp data.example.csv data.csv          # then put your switches in data.csv
./tree-li --check                     # validates config + switch list
./tree-li
```

To start it from anywhere, add an alias (the script finds its files even through a symlink):

```bash
echo "alias tree-li='$HOME/tree-li/tree-li'" >> ~/.bashrc
```

**Shared by a team** (no system-wide install needed): put the directory where
your colleagues can read it, e.g. `/srv/netops/tree-li`, with one `data.csv`
and an optional `tree-li.conf`. Everyone starts the same `tree-li`.
Credentials and session logs stay per user.

> If you copied the files through Windows and get `python3\r: No such file or directory`
> or `Permission denied`, run `python3 tree-li` or fix the file with `sed -i 's/\r$//' tree-li; chmod +x tree-li`.

## Switch list (`data.csv`)

The format is the same as V-Li: `;`-separated, first line is the header.

```csv
Name;IP;subnet;aliases;comment;type;id;responsible;aix_server
ber-core-01;192.0.2.1;ber;Core switch Berlin;5520;core;101;Ruffy;-
```

- `Name` and `IP` are what TRee-Li really needs. Header names are case-insensitive.
- The delimiter (`;` `,` `|` tab) is detected automatically. UTF-8 (with or without BOM) and Excel/Windows encoding both work.
- Empty lines and lines starting with `#` are ignored.
- **Adding columns** (e.g. `location`): add them to the CSV. They appear in **details** right away.
  To show and search them in the table, list them in `columns` in `tree-li.conf`, e.g.
  `columns = Name, IP, location:Where, aliases:Alias, comment`
- `data.csv` and `tree-li.conf` are in `.gitignore`, so your switch inventory never ends up on GitHub.

## Configuration

Everything is optional. See [`tree-li.conf.example`](tree-li.conf.example) for all options. Files are read in this order (later ones win):

1. `tree-li.conf` next to the `tree-li` script: team defaults
2. `~/.config/tree-li/tree-li.conf`: your personal settings
3. `--config FILE`

Command line options: `--data CSV`, `--user NAME`, `--log`, `--ascii`, `--config FILE`, `--check`, `--version`.
The environment variable `TREELI_DATA` also sets the switch list.

### Session logging (off by default)

Start with `tree-li --log` or set `session_log = yes`. Each ssh session is written to
`~/.local/state/tree-li/logs/<date>-<time>_<switch>.log` (mode 0600, only you can read it).
The log contains what was shown on screen. The password TRee-Li types is never in it.
Be aware that commands like `show running-config` can include secrets.

## Security notes

- The password is kept **only in the memory** of the running TRee-Li process. It never goes to disk,
  command-line arguments or environment variables, and other users can't see it in `ps`.
  Quitting TRee-Li forgets it.
- TRee-Li types the password **only once per connection**, and only at a real password prompt.
  It never answers SSH-key passphrase prompts. When a password is wrong,
  ssh is stopped right away instead of retrying, the stored password is wiped and you are asked again.
  This protects a central (TACACS+/RADIUS) account from being locked out.
- Once you type anything in a session, TRee-Li stops watching the output. A later
  `Password:` prompt on the switch is never answered automatically.
- New switches are added to `~/.ssh/known_hosts` automatically (`accept-new`).
  If a switch's host key **changes**, ssh refuses the connection and TRee-Li asks before removing the old key.
  That's expected after a hardware swap, but can also mean an attack.
- Values from the CSV are never passed through a shell. Hosts that look like command-line options
  (e.g. `-oProxyCommand=...`) are rejected.

## Troubleshooting

| Problem | Fix |
|---|---|
| `switch list not found` | `cp data.example.csv data.csv`, or set `data =` in `tree-li.conf` |
| Old switch: `no matching key exchange method` / `host key type` | Add e.g. `ssh_options = -o KexAlgorithms=+diffie-hellman-group14-sha1 -o HostKeyAlgorithms=+ssh-rsa` in `tree-li.conf`. On RHEL 9 the system crypto policy may also need to allow SHA-1 |
| F-keys don't sort | Use `Tab` / `Shift-Tab` |
| Lines or symbols look garbled (`â”€`, `?`) | Start with `tree-li --ascii`, or set `charset = ascii` in `tree-li.conf`. In PuTTY you can also set *Window > Translation* to UTF-8 |
| Only a few colours in PuTTY | Set *Connection > Data > Terminal-type string* to `xterm-256color` |
| Garbled screen | Press `Ctrl-L`, or check that `TERM` is set (`xterm-256color` for Tabby, `xterm` for PuTTY) |
| Check everything at once | `tree-li --check` |

## Development

```bash
python3 -m unittest discover -s tests -v
```

`tests/fake_ssh.py` acts as a switch (password `secret`, a changed host key, a timeout).
To use it, point `ssh_command` at it in a test config.
