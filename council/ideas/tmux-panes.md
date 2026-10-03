# Idea: several switches at once in tmux panes

**Status:** on hold (2026-10-03). The user wants **option 1** (one login via a handover) but first researches whether the
remaining risks are acceptable. **Nothing of this is built.** First code sketch: [tmux-panes-draft.py](tmux-panes-draft.py)
(untested, without the hardening below).

## How it would be used
1. Open TRee-Li normally, **outside** tmux.
2. **One** switch: Enter connects as today, inside TRee-Li. Nothing changes.
3. **Two or more:** mark them with **Tab** (fzf-style; `Shift-Tab` unmarks moving up). With the mouse, right-click a row or
   click its left edge. Marked rows get a `+`, and the top bar shows "3 marked".
4. Choose **ssh** and press Enter. TRee-Li starts its own tmux session (`tree-li-HHMMSS`) with **one pane per switch**
   in **one window**, tiled, at most **9** panes. All panes log in **at the same time**: a mistyped password is the user's
   problem, as when using tmux by hand.
5. You are now in tmux, with normal tmux controls. **`Ctrl-b d`** detaches and you're back in TRee-Li. If you log out of all
   panes, the session ends and you're also back. `Ctrl-T` in TRee-Li would reattach to the session.
6. **Batch ping** pings only the marked switches when some are marked (agreed, no tmux needed).
7. Inside an existing tmux (`$TMUX` set), tmux refuses nesting by default, so TRee-Li would open a new **window** in the
   current session instead. Back with `Ctrl-b l`.
8. tmux's "type into all panes" (`synchronize-panes`) is forced **off** for this window.

## Handover channel (option 1)
Panes are started by tmux, not by TRee-Li. Their command line is visible to every user (`ps`), so the password can't go
there, nor into environment variables or a file. Instead:
1. **Private folder:** TRee-Li creates `$XDG_RUNTIME_DIR/tree-li/` (`/run/user/<uid>`, in RAM, mode 0700, removed at
   logout; fallback `/tmp/tree-li-<uid>`, owner and mode checked). In it, a Unix socket `handover-<pid>.sock` (0600).
2. **Ticket per pane:** a random 128-bit one-time ticket, passed on the pane's command line
   (`tree-li --pane <socket> <ticket> <host> <name>`).
3. **Fetching the password:** the pane connects. The kernel reports the peer's uid and pid (`SO_PEERCRED`). TRee-Li answers
   once with user and password if the uid is ours, the ticket is valid and unused, and the switch matches.
4. **Logging in:** the pane types the password like today (once, aborting on a second prompt) and forgets it.
5. **Reporting back:** at the end, the pane reports ok / failed / login failed via its ticket, so the SSH column and the
   recent list are updated, and the stored password is wiped on a login failure.

## Security assessment (Warden, brutally honest)
| Attacker | Gets the password? |
|---|---|
| Other users | no, if implemented correctly (folder, socket, kernel uid check) |
| Processes of the **same user** | without hardening yes (read a ticket from `ps`, race the pane). With pid binding they'd need to read process memory instead, and `PR_SET_DUMPABLE=0` blocks that too (built, D21) |
| root | yes, as with every tool |
| Network | no, Unix sockets are local only |

**The real, new risks:**
1. **New, self-written security code** (about 80 lines). This is the biggest risk. The pattern is proven (`ssh-agent`,
   `gpg-agent`), the implementation isn't. It should be reviewed before colleagues use it.
2. The password sits briefly in up to 9 more processes. Python can't reliably wipe memory.
3. Crash dumps could contain it. **Fixed for TRee-Li already** (D21: core dumps off).
4. The ticket window between a pane starting and fetching. Closed by the hardening below.
5. **Forgotten background sessions (the Warden's main concern, shared by the user):** after `Ctrl-b d`, up to 9 logged-in
   admin sessions keep running until the switches' idle timeout. Requirements if built:
   - TRee-Li shows **"N tmux sessions running"** prominently in the top bar
   - an **idle timeout** forgets the stored password
   - consider closing TRee-Li's sessions when TRee-Li exits (or asking)
6. **Company policy** may forbid passing credentials between processes. Check before rolling out.

**Mandatory hardening if built:**
- the ticket is bound to the **pane's process ID**: `tmux split-window -P -F "#{pane_pid}"`, compared with `SO_PEERCRED`'s
  pid or its parent
- ticket lifetime **10 s**
- the socket is open only while panes are starting, then closed and deleted
- core dumps off and not dumpable (already done for the main TRee-Li)

## Alternatives (if option 1 is rejected)
- **Option 2:** same panes, but **each pane asks for the password itself**. No new attack surface, more typing.
- **Option 3:** no feature. Run two TRee-Li copies in tmux by hand, which works today.

## Effort estimate
About 250–300 lines (marking, pane opener, `--pane` mode, handover, report-back) plus tests. tmux is installed on the
server, and the initiators use it.
