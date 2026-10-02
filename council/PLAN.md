# Current Plan (Drafter)

## Milestone 1: working tool. DONE (2026-10-02)
1. [x] `tree-li` single file: config, CSV loading, search, sort
2. [x] curses UI matching V-Li: title, command bar, search, table, status line
3. [x] Own key parser (PuTTY `ESC[11~`, xterm `ESC OP`, Linux console `ESC[[A`)
4. [x] Popups: ping (streamed), traceroute/tracepath (streamed), details, help
5. [x] Batch ping: thread pool (64), ESC cancels, `Ping` column, F6 sorts DOWN first
6. [x] Credential dialog, pty ssh relay, handling of auth failures and changed host keys
7. [x] Optional session log (0600, never contains the password)
8. [x] Tests: 36 (logic, ssh relay against `tests/fake_ssh.py` through a pty, tmux UI smoke test); Python 3.8/3.9/3.11/3.14
9. [x] README, `data.example.csv`, `tree-li.conf.example`, `.gitignore`, `.gitattributes`

## Milestone 1b: review fixes + redesign. DONE (2026-10-02)
- [x] All 10 review findings fixed (see code-review), 38 tests
- [x] Redesign per D11; verified in 256 colours, 8 colours and ASCII
- [x] Restored `.gitignore` / `.gitattributes` (missing from the first push!)

## Milestone 1c: brainstorm picks #1 + #2. DONE (2026-10-02)
- [x] Search filters (D12), highlighted in the search line, documented in help + README
- [x] Favourites (Ctrl-F, pinned, `is:fav`) and history (`is:recent`, "Last connected" in details)
- [x] 46 tests

## Milestone 2: field test (needs the user)
- [ ] Run `./tree-li --check` on the RHEL server
- [ ] ssh into a real Extreme Fabric Engine switch: password prompt detected? logout returns to the menu?
- [ ] Try a wrong password once: one attempt only, then asked again
- [ ] Try it from PuTTY (F-keys, colours, Unicode lines) and from Tabby
- [ ] Batch ping over all ~700 switches: duration acceptable?

## Backlog (brainstorm, not yet chosen)
- #3 tmux: ssh in new tmux windows (needs a private password hand-over socket)
- #4 data checks in `--check` + startup hint (duplicates, column count, invalid IPs)
- #5 wrong-IP warning (prompt hostname vs CSV name)
- #6/#7 run show commands on many switches / config backup (read-only by default)
- #8 LLDP neighbours, #9 live monitor, #10 idle password timeout, #11 personal connection log
- Tree view by site, mouse support, copy IP, CSV export

## Backlog (only if asked)
- Extra CSV columns (location, ...): configure `columns`, no code change needed
- Change the username mid-session (today: restart TRee-Li)
