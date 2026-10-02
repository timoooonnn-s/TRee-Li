"""End-to-end smoke test: the real curses UI in a tmux pane, ssh = tests/fake_ssh.py.
Skipped when tmux is not installed."""
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION = "treeli-test-%d" % os.getpid()


def tmux(*args):
    return subprocess.run(["tmux"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          check=False).stdout.decode("utf-8", "replace")


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class UiSmokeTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "data.csv"), "w") as f:
            f.write("Name;IP;subnet;aliases;comment\n"
                    "fake-good;10.99.0.1;lab;Good switch;pw secret\n"
                    "fake-dead;10.99.0.3;lab;Dead switch;timeout\n"
                    "sw10;192.0.2.10;ber;Core Berlin;\n")
        conf = os.path.join(self.tmp, "test.conf")
        with open(conf, "w") as f:
            f.write("[tree-li]\ndata = data.csv\nuser = timmy\nssh_command = %s %s\n"
                    % (sys.executable, os.path.join(ROOT, "tests", "fake_ssh.py")))
        cmd = "env HOME=%s XDG_CONFIG_HOME=%s TERM=xterm %s %s --config %s; echo EXITED; sleep 30" % (
            shlex.quote(self.tmp), shlex.quote(self.tmp), shlex.quote(sys.executable),
            shlex.quote(os.path.join(ROOT, "tree-li")), shlex.quote(conf))
        tmux("new-session", "-d", "-s", SESSION, "-x", "110", "-y", "30", cmd)
        self.wait_for("TRee-Li")

    def tearDown(self):
        tmux("kill-session", "-t", SESSION)
        shutil.rmtree(self.tmp)

    def screen(self):
        return tmux("capture-pane", "-p", "-t", SESSION)

    def keys(self, *keys, literal=False):
        tmux("send-keys", "-t", SESSION, *(["-l"] if literal else []), *keys)
        time.sleep(0.3)

    def wait_for(self, text, timeout=8):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if text in self.screen():
                return
            time.sleep(0.1)
        self.fail("%r not on screen:\n%s" % (text, self.screen()))

    def test_search_ssh_and_back(self):
        self.keys("sw10", literal=True)
        self.assertNotIn("fake-good", self.screen())
        # ESC and a key in the same burst: search is cleared AND the key is kept
        self.keys("\x1bf", literal=True)
        self.wait_for("Search: f")
        self.keys("C-u")
        self.keys("Enter")                       # ssh is the default command
        self.wait_for("Username:")
        self.keys("secret", literal=True)
        self.keys("Enter")
        self.wait_for("FAKE-SW:1>")
        self.keys("exit", literal=True)
        self.keys("Enter")
        self.wait_for("Disconnected from fake-good")
        self.keys("Left", "Enter")               # "exit" is left of "ssh" (the bar wraps)
        self.wait_for("credentials forgotten")

    def test_failed_connection_pauses(self):
        self.keys("dead", literal=True)
        self.keys("Enter")
        self.wait_for("Username:")
        self.keys("secret", literal=True)
        self.keys("Enter")
        self.wait_for("Press any key")
        self.keys("x")
        self.wait_for("ssh exit code 255")       # the reason is also shown in the status line


if __name__ == "__main__":
    unittest.main()
