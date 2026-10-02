"""ssh_check and the combined batch check, against tiny local test servers."""
import socket
import threading
import time
import types
import unittest

from test_tree_li import tl


def server(behaviour):
    """Listen on 127.0.0.1; behaviour: 'ssh' greets like sshd, 'ssh-late' waits for the
    client first, 'silent' accepts and says nothing.  Returns (port, closer)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    stop = []

    def run():
        srv.settimeout(0.2)
        while not stop:
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                if behaviour == "ssh":
                    conn.sendall(b"SSH-2.0-OpenSSH_test\r\n")
                elif behaviour == "ssh-late":
                    conn.settimeout(3)
                    if conn.recv(64).startswith(b"SSH-"):
                        conn.sendall(b"SSH-2.0-late\r\n")
                time.sleep(0.3)
    t = threading.Thread(target=run, daemon=True)
    t.start()

    def close():
        stop.append(1)
        srv.close()
    return srv.getsockname()[1], close


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class SshCheckTest(unittest.TestCase):
    def test_states(self):
        for behaviour, expected in (("ssh", tl.SSH_OPEN), ("ssh-late", tl.SSH_OPEN), ("silent", tl.SSH_SILENT)):
            port, close = server(behaviour)
            try:
                self.assertEqual(tl.ssh_check("127.0.0.1", port, 1), expected, behaviour)
            finally:
                close()
        self.assertEqual(tl.ssh_check("127.0.0.1", free_port(), 1), tl.SSH_CLOSED)
        self.assertEqual(tl.ssh_check("no-such-host.invalid", 22, 1), tl.SSH_SILENT)

    def test_batch_check(self):
        port, close = server("ssh")
        try:
            cfg = types.SimpleNamespace(ping_workers=4, ping_timeout=1, ssh_port=port, ssh_check_timeout=1)
            ping, ssh = {}, {}
            batch = tl.BatchCheck(["127.0.0.1"], cfg, ping, ssh)
            for _ in range(100):
                if not batch.running:
                    break
                time.sleep(0.05)
            self.assertEqual(ping, {"127.0.0.1": tl.PING_UP})
            self.assertEqual(ssh, {"127.0.0.1": tl.SSH_OPEN})
            self.assertEqual(batch.percent, 100)
            self.assertIn("1 open", batch.summary())
        finally:
            close()


if __name__ == "__main__":
    unittest.main()
