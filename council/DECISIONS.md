# Decisions

Each entry records who proposed it, who objected, and the outcome.

## D1: Name: **TRee-Li** (2026-10-02)
Spelled **TRee-Li**: T + R for Timmy and Ruffy. "Tree" fits a network tool, and "-Li" keeps the V-Li family name.
The command is `tree-li` (`tree` already exists on Linux, so the hyphenated name doesn't collide).

## D2: Python 3, standard library only, one executable file
- Target: RHEL with Python 3.11. Tested with Python 3.8, 3.9, 3.11 and 3.14. RHEL 9's default `python3` is 3.9, so 3.8+ compatibility is required.
- No pip, no venv. To install, copy one file.
- Rejected: Bash + whiptail (no live search table, no password injection), Go (needs libraries and a toolchain).

## D3: SSH through the system `ssh` binary in a pseudo-terminal (`pty`)
- The tool watches for the password prompt and types the password once. After that it relays I/O transparently.
- The password lives only in process memory. It never goes to disk, argv or env, and it's gone when the tool exits.
- Credentials are asked lazily, on the first `ssh` of a session. The username is pre-filled with the Linux user and can be edited.
- Leaving the password empty means the tool never types it, and ssh asks as usual (key users, testing).
- *Warden:* `passphrase` prompts (SSH key) and MFA/other prompts are **never** auto-answered.
- *Warden:* `NumberOfPasswordPrompts=1`. If a second password prompt appears, the attempt is aborted, the stored password is wiped and the user is asked again. This prevents locking out a TACACS/RADIUS account across 700 switches.

## D4: Host keys
- `StrictHostKeyChecking=accept-new`: new switches are accepted silently.
- When a stored key has changed (device replaced), TRee-Li asks y/N and then runs `ssh-keygen -R`. It never removes a key silently (*Warden*).

## D5: After disconnect, return to the menu
- After a normal logout the main screen comes back immediately.
- When ssh itself fails (exit code 255: timeout, refused, unreachable), the error stays on screen until a key is pressed (*Operator*).
- `ServerAliveInterval` makes dead sessions come back on their own.

## D6: UI follows V-Li
- Same order of elements: title, command bar, search, table, status line.
- Same commands: `ssh · ping · traceroute · batch ping · details · help · exit`. Same keys.
- `traceroute` runs `traceroute` if it's installed, otherwise `tracepath` (the server only has tracepath).
- `batch ping` writes UP/DOWN into a `Ping` column, which is sortable.
- *Critic/Operator:* TRee-Li parses escape sequences itself, so F1–F6 work in PuTTY's default mode too. `Tab` cycles the sort column as a backup.
- Only ASCII is used for the UI chrome. PuTTY line-drawing characters break with UTF-8, so there are none.

## D7: Data & config
- Same CSV format as V-Li. The delimiter is auto-detected. UTF-8 (including a BOM) is accepted, with a fallback to cp1252 (Excel on Windows).
- The data path is resolved relative to the config file or the script, **never the CWD** (V-Li bug).
- Shared defaults live in `tree-li.conf` next to the script. Personal overrides go in `~/.config/tree-li/tree-li.conf`.
- Visible columns are configurable, so future CSV columns (e.g. location) can be added without code changes.

## D8: Session logging: optional, off by default
- Turned on with the `--log` flag or `session_log = yes`.
- Logs are per user, in `~/.local/state/tree-li/logs`, with modes 0700/0600. Never in the shared directory (*Warden*).

## D9: Normal logout vs. failure (Operator + Critic, 2026-10-02)
- Many switches end the session with ssh exit code 255 ("closed by remote host"), so the exit code alone can't tell a normal logout from a failure.
- Rule: if the user typed anything after the login, it was a session. TRee-Li returns to the menu immediately and shows "Disconnected".
- If the user never typed anything and the exit code is non-zero, it was a connection failure. TRee-Li waits for a key so the error stays readable, and also shows it in the status line.

## D10: Repository hygiene (Warden)
- `data.csv` and `tree-li.conf` are git-ignored. The real inventory never goes to GitHub; `data.example.csv` and `tree-li.conf.example` are shipped instead.
- `.gitattributes` forces LF line endings, because the repo travels through Windows and a CRLF shebang breaks.
