#!/usr/bin/env python3
"""Stand-in for `ssh` in the tests: behaves like a switch, chosen by host.

  10.99.0.1  password "secret", then a small CLI ("exit" ends the session with
             exit code 255 like many switches do; "pwtest" prints a password prompt;
             "denied" prints "Permission denied" like a rejected command)
  10.99.0.2  host key changed while $HOME/.ssh/known_hosts mentions 10.99.0.2
  10.99.0.3  connection timeout
Every invocation's argv is appended to $FAKE_SSH_ARGV (if set).
"""
import os
import sys
import termios
import time


def read_secret(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] &= ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    try:
        line = sys.stdin.readline()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.stdout.write("\n")
    return line.rstrip("\r\n")


def main():
    args = sys.argv[1:]
    if os.environ.get("FAKE_SSH_ARGV"):
        with open(os.environ["FAKE_SSH_ARGV"], "a") as f:
            f.write(repr(args) + "\n")
    host = args[-1]
    user = args[args.index("-l") + 1] if "-l" in args else "nobody"
    one_try = "NumberOfPasswordPrompts=1" in args

    if host == "10.99.0.3":
        time.sleep(0.5)
        sys.stderr.write("ssh: connect to host %s port 22: Connection timed out\n" % host)
        return 255
    if host == "10.99.0.2":
        kh = os.path.join(os.path.expanduser("~"), ".ssh", "known_hosts")
        if os.path.exists(kh) and host in open(kh).read():
            sys.stderr.write(
                "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @\n"
                "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "Offending ED25519 key in %s:1\n"
                "Host key verification failed.\n" % kh)
            return 255

    tries = 0
    while True:
        tries += 1
        pw = read_secret("%s@%s's password: " % (user, host))
        if pw == "secret":
            break
        if one_try or tries >= 3:
            sys.stderr.write("%s@%s: Permission denied (publickey,keyboard-interactive).\n" % (user, host))
            return 255
        sys.stdout.write("Permission denied, please try again.\n")

    sys.stdout.write("\nExtreme Networks Fabric Engine (fake)\n\nFAKE-SW:1>")
    sys.stdout.flush()
    for line in sys.stdin:
        cmd = line.strip()
        if cmd in ("exit", "logout"):
            sys.stdout.write("Connection to %s closed by remote host.\n" % host)
            return 255
        if cmd == "pwtest":
            sys.stdout.write("Enter password:")
            sys.stdout.flush()
            sys.stdout.write("\ngot %r\nFAKE-SW:1>" % sys.stdin.readline().strip())
        elif cmd == "denied":
            sys.stdout.write("Permission denied\nFAKE-SW:1>")
        elif cmd:
            sys.stdout.write("you typed: %s\nFAKE-SW:1>" % cmd)
        else:
            sys.stdout.write("FAKE-SW:1>")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
