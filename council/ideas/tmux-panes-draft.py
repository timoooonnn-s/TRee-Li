# DRAFT - NOT PART OF TRee-Li, NOT TESTED, NOT IMPORTED ANYWHERE.
# First sketch of the tmux pane feature (see tmux-panes.md), kept so the work is not lost.
# Before using any of it: add the hardening listed in tmux-panes.md (ticket bound to the
# pane's process ID, 10 s ticket lifetime, socket only open while panes start) and review it.
# It also needs: import json, secrets, socket - and the marking / open / attach code in App.

# --------------------------------------------------------------------------
# Around an ssh session (outside curses): notes, logs, host keys
# --------------------------------------------------------------------------

def note_text(lines, colors=True, gt=">"):
    """'TRee-Li > first line', further lines indented - printed outside curses."""
    prefix = "\033[1;34mTRee-Li\033[0m" if colors else "TRee-Li"     # bold blue: every colour terminal knows it
    return "\r\n%s %s %s" % (prefix, gt, ("\r\n" + " " * 10).join(lines))


def open_session_log(cfg, name, host, user):
    """--log: a new log file (0600) for one session.  Returns (file or None, error or None)."""
    try:
        os.makedirs(cfg.log_dir, mode=0o700, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name or host)[:60]
        path = os.path.join(cfg.log_dir, "%s_%s.log" % (time.strftime("%Y%m%d-%H%M%S"), safe))
        f = os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab")
        f.write(("# TRee-Li session log: %s (%s) as %s, %s\n"
                 % (name, host, user, time.strftime("%Y-%m-%d %H:%M:%S"))).encode("utf-8"))
        return f, None
    except OSError as e:
        return None, "cannot write session log: %s" % e


def write_debug_report(cfg, name, host, argv, password, result):
    """--debug: append what happened around this login to debug.log (0600): the ssh
    command, prompts, decisions and the output BEFORE the login - never the password,
    never the session itself.  Returns an error text or None."""
    lines = [
        "=== %s  %s (%s)" % (time.strftime("%Y-%m-%d %H:%M:%S"), name, host),
        "command      : %s" % " ".join(shlex.quote(a) for a in argv),
        "password     : %s" % ("stored, TRee-Li types it" if password else "none stored, you type it"),
    ] + ["event        : %s" % e for e in result.events] + [
        "exit code    : %s   failed: %s   auth failed: %s   host key changed: %s" % (
            result.exit_code, result.failed, result.auth_failed, result.hostkey_changed),
        "last line    : %s" % result.last_line,
        "before login :",
    ] + ["  | " + line for line in result.pre_login.strip("\n").split("\n")[-40:]] + [""]
    path = os.path.join(cfg.state_dir, "debug.log")
    try:
        os.makedirs(cfg.state_dir, mode=0o700, exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return None
    except OSError as e:
        return "cannot write %s: %s" % (path, e.strerror or e)


def ssh_flow(cfg, name, host, user, password, note, back="return to TRee-Li"):
    """One ssh connection outside curses, used by the main screen and by tmux panes:
    connect (typing the password once), offer to replace a changed host key, and
    wait for a key after a failure so the reason stays readable.  Returns SessionResult."""
    out = sys.stdout.fileno()

    def say(*lines):
        os.write(out, note(*lines).encode("utf-8", "replace"))
    key_removed = False
    while True:
        argv = build_ssh_argv(cfg, user, host, inject_password=bool(password))
        say("Connecting to %s (%s) as %s" % (name, host, user), "log out to %s, ~. force-disconnects" % back)
        os.write(out, b"\r\n\r\n")
        log = None
        if cfg.session_log:
            log, error = open_session_log(cfg, name, host, user)
            if error:
                say(error)
        try:
            result = run_session(argv, password, log)
        finally:
            if log is not None:
                log.close()
        if cfg.debug:
            error = write_debug_report(cfg, name, host, argv, password, result)
            if error:
                say(error)
        if result.hostkey_changed and not result.auth_failed:
            known_hosts = result.known_hosts or os.path.join(os.path.expanduser("~"), ".ssh", "known_hosts")
            if key_removed:
                terminal_wait_key(note("The host key is still reported as changed.",
                                       "Please check %s by hand." % known_hosts, "Press any key to %s ..." % back))
                return result
            answer = terminal_wait_key(note(
                "The host key of %s (%s) has CHANGED." % (name, host),
                "Expected if the switch was replaced - otherwise do NOT continue.",
                "Remove the old key from %s and connect again? [y/N] " % known_hosts))
            if answer not in (b"y", b"Y"):
                return result
            ok, text = remove_host_key(host, known_hosts)
            os.write(out, (text.replace("\n", "\r\n") + "\r\n").encode("utf-8", "replace"))
            if not ok:
                terminal_wait_key(note("Could not remove the old key.", "Press any key to %s ..." % back))
                return result
            key_removed = True
            continue
        if result.failed and not result.auth_failed:
            terminal_wait_key(note("Connection to %s ended (exit code %d)." % (name, result.exit_code),
                                   "Press any key to %s ..." % back))
        return result


# --------------------------------------------------------------------------
# Several switches at once: one tmux session, one pane per switch.
# The panes get the password from the running TRee-Li through a private,
# one-time handover (never through the command line, environment or a file).
# --------------------------------------------------------------------------

MAX_PANES = 9
TMUX_SESSION_PREFIX = "tree-li-"


def runtime_dir():
    """A private folder for the handover socket: $XDG_RUNTIME_DIR/tree-li (RAM, per user,
    removed at logout), otherwise /tmp/tree-li-<uid>.  Must belong to us and be mode 0700."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    path = os.path.join(base, "tree-li") if base and os.path.isdir(base) else "/tmp/tree-li-%d" % os.getuid()
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    st = os.lstat(path)
    if not stat_is_private_dir(st):
        raise OSError("%s is not a private directory (owner/mode)" % path)
    return path


def stat_is_private_dir(st):
    import stat as st_mod
    return st_mod.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and st.st_mode & 0o077 == 0


def peer_uid(conn):
    """The user id of the process at the other end of a Unix socket (from the kernel)."""
    if hasattr(socket, "SO_PEERCRED"):                       # Linux
        creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return struct.unpack("3i", creds)[1]
    creds = conn.getsockopt(0, 0x001, 76)                      # macOS / BSD: LOCAL_PEERCRED -> xucred
    return struct.unpack("2I", creds[:8])[1]


class Handover(object):
    """Hands username + password to tmux panes, once per pane.

    Every pane gets a random one-time ticket on its command line.  The ticket is
    useless without the socket, which lives in a folder only we can open; the
    kernel also tells us which user connects, and only our own user is answered.
    A ticket gives the password once (within 60 s) and may report the result once."""

    TICKET_LIFETIME = 60

    def __init__(self, credentials):
        self.credentials = credentials           # function -> (user, password or None)
        self.path = os.path.join(runtime_dir(), "handover-%d.sock" % os.getpid())
        if os.path.exists(self.path):
            os.unlink(self.path)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old = os.umask(0o177)
        try:
            self.server.bind(self.path)          # created as 0600
        finally:
            os.umask(old)
        self.server.listen(16)
        self.tickets = {}                        # ticket -> {"host", "created", "fetched"}
        self.results = []                        # (host, state, reason) reported by panes
        self.lock = threading.Lock()
        t = threading.Thread(target=self._serve)
        t.daemon = True
        t.start()

    def issue(self, host):
        ticket = secrets.token_hex(16)
        with self.lock:
            self.tickets[ticket] = {"host": host, "created": time.time(), "fetched": False}
        return ticket

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return                           # closed
            with conn:
                try:
                    conn.settimeout(5)
                    if peer_uid(conn) != os.getuid():
                        continue
                    request = conn.recv(4096).decode("utf-8", "replace").strip()
                    conn.sendall(self._answer(request).encode("utf-8") + b"\n")
                except (OSError, ValueError, struct.error):
                    pass

    def _answer(self, request):
        kind, _, rest = request.partition(" ")
        ticket, _, rest = rest.partition(" ")
        with self.lock:
            entry = self.tickets.get(ticket)
            if entry is None:
                return "ERR unknown ticket"
            if kind == "GET" and not entry["fetched"] and time.time() - entry["created"] < self.TICKET_LIFETIME:
                entry["fetched"] = True
                user, password = self.credentials()
                return "OK " + json.dumps({"user": user, "password": password or ""})
            if kind == "DONE" and entry["fetched"]:
                state, _, reason = rest.partition(" ")
                self.results.append((entry["host"], state, reason))
                del self.tickets[ticket]
                return "OK"
        return "ERR refused"

    def take_results(self):
        with self.lock:
            results, self.results = self.results, []
        return results

    def close(self):
        try:
            self.server.close()
            os.unlink(self.path)
        except OSError:
            pass


def handover_request(path, line):
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.settimeout(5)
    try:
        conn.connect(path)
        conn.sendall(line.encode("utf-8") + b"\n")
        answer = b""
        while not answer.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                break
            answer += chunk
        return answer.decode("utf-8", "replace").strip()
    finally:
        conn.close()


def pane_main(cfg, path, ticket, host, name):
    """`tree-li --pane ...`: runs inside one tmux pane - fetch the login once, connect,
    report the result back, then the pane closes."""
    colors = os.environ.get("TERM", "dumb") != "dumb"
    gt = CHARSETS[detect_charset(cfg.charset_setting)]["gt"]

    def note(*lines):
        return note_text(lines, colors, gt)
    os.write(sys.stdout.fileno(), ("\033]2;%s\033\\" % name).encode("utf-8", "replace"))   # pane title
    if not valid_host(host):
        terminal_wait_key(note("'%s' is not a usable host." % host, "Press any key to close this pane ..."))
        return 1
    try:
        answer = handover_request(path, "GET %s" % ticket)
        if not answer.startswith("OK "):
            raise ValueError(answer)
        login = json.loads(answer[3:])
    except (OSError, ValueError) as e:
        terminal_wait_key(note("Could not get the login from TRee-Li (%s)." % e, "Press any key to close this pane ..."))
        return 1
    result = ssh_flow(cfg, name, host, login["user"], login["password"] or None, note, back="close this pane")
    login = None                                  # the password is not needed any more
    if result.auth_failed:
        state, reason = "authfail", "login failed - wrong password?"
        terminal_wait_key(note("Login failed on %s - wrong password?" % name, "Press any key to close this pane ..."))
    elif result.failed or result.hostkey_changed:
        state, reason = SSH_FAILED, "exit code %d - %s" % (result.exit_code, result.last_line)
    else:
        state, reason = SSH_OK, ""
    try:
        handover_request(path, "DONE %s %s %s" % (ticket, state, reason))
    except OSError:
        pass                                      # TRee-Li was closed meanwhile - nothing to report to
    return 0


def tmux(*args):
    """Run a tmux command; returns its output (stripped) or raises RuntimeError."""
    proc = subprocess.run(["tmux"] + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or "tmux failed")
    return proc.stdout.decode("utf-8", "replace").strip()


def tree_li_sessions():
    """Names of TRee-Li's tmux sessions that are still running, newest last."""
    try:
        names = tmux("list-sessions", "-F", "#{session_created} #{session_name}").splitlines()
    except (RuntimeError, OSError):
        return []
    return [n.split(" ", 1)[1] for n in sorted(names) if n.split(" ", 1)[-1].startswith(TMUX_SESSION_PREFIX)]


