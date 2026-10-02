"""Unit tests for the logic in tree-li (stdlib unittest only).

Run from the repository root:  python3 -m unittest discover -s tests -v
"""
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader = importlib.machinery.SourceFileLoader("treeli", os.path.join(ROOT, "tree-li"))
_spec = importlib.util.spec_from_loader("treeli", _loader)
tl = importlib.util.module_from_spec(_spec)
_loader.exec_module(tl)


def args(**kw):
    base = dict(config=None, data=None, user=None, log=False, check=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._env = dict(os.environ)
        os.environ["XDG_CONFIG_HOME"] = os.path.join(self.tmp, "xdg")   # ignore the real user config
        os.environ.pop("TREELI_DATA", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp)

    def write(self, name, content, mode="w", encoding="utf-8"):
        path = os.path.join(self.tmp, name)
        if "b" in mode:
            with open(path, mode) as f:
                f.write(content)
        else:
            with open(path, mode, encoding=encoding, newline="") as f:
                f.write(content)
        return path


class TestCsv(TempDir):
    def test_semicolon_with_bom_and_comments(self):
        p = self.write("a.csv", "﻿Name;IP;comment\n# comment line\n\nsw1;10.0.0.1;Zürich\n")
        headers, rows = tl.read_table(p)
        self.assertEqual(headers, ["Name", "IP", "comment"])
        self.assertEqual(rows, [{"Name": "sw1", "IP": "10.0.0.1", "comment": "Zürich"}])

    def test_comma_autodetect_crlf_and_quotes(self):
        p = self.write("b.csv", 'Name,IP,comment\r\nsw1,10.0.0.1,"a, b"\r\n')
        _, rows = tl.read_table(p)
        self.assertEqual(rows[0]["comment"], "a, b")

    def test_cp1252_fallback(self):
        p = self.write("c.csv", "Name;IP;comment\nsw1;10.0.0.1;Gr\xfcezi\n".encode("cp1252"), mode="wb")
        _, rows = tl.read_table(p)
        self.assertEqual(rows[0]["comment"], "Grüezi")

    def test_short_and_long_rows_and_control_chars(self):
        p = self.write("d.csv", "Name;IP;comment\nsw1;10.0.0.1\nsw2;10.0.0.2;x\ty;extra\n")
        _, rows = tl.read_table(p)
        self.assertEqual(rows[0]["comment"], "")
        self.assertEqual(rows[1]["comment"], "x y")

    def test_missing_and_empty(self):
        with self.assertRaises(tl.DataError):
            tl.read_table(os.path.join(self.tmp, "nope.csv"))
        with self.assertRaises(tl.DataError):
            tl.read_table(self.write("e.csv", "\n\n"))

    def test_build_devices_case_insensitive_and_warnings(self):
        p = self.write("f.csv", "name;ip;Subnet;aliases;location\nsw1;10.0.0.1;a;Core;Room 1\n")
        cfg = tl.load_config(args())
        devices, columns, warns = tl.build_devices(*tl.read_table(p), cfg=cfg)
        self.assertEqual(devices[0].host, "10.0.0.1")
        self.assertEqual(devices[0].name, "sw1")
        self.assertEqual([c[1] for c in columns], ["Name", "IP", "subnet", "Alias"])
        self.assertTrue(any("comment" in w for w in warns))

    def test_no_ip_column(self):
        p = self.write("g.csv", "Name;where\nsw1;x\n")
        cfg = tl.load_config(args())
        with self.assertRaises(tl.DataError):
            tl.build_devices(*tl.read_table(p), cfg=cfg)


class TestConfig(TempDir):
    def test_defaults_resolve_data_next_to_script(self):
        cfg = tl.load_config(args())
        self.assertEqual(cfg.data, os.path.join(tl.SCRIPT_DIR, "data.csv"))
        self.assertIsNone(cfg.delimiter)
        self.assertFalse(cfg.session_log)

    def test_config_file_relative_data_and_overrides(self):
        conf = self.write("my.conf", "[tree-li]\ndata = lists/sw.csv\ndelimiter = ;\n"
                          "columns = Name, location:Where\nsession_log = yes\nuser = netadmin\n")
        cfg = tl.load_config(args(config=conf))
        self.assertEqual(cfg.data, os.path.join(self.tmp, "lists", "sw.csv"))
        self.assertEqual(cfg.delimiter, ";")
        self.assertEqual(cfg.columns, [("Name", "Name"), ("location", "Where")])
        self.assertTrue(cfg.session_log)
        self.assertEqual(cfg.user, "netadmin")
        self.assertEqual(tl.load_config(args(config=conf, user="other")).user, "other")

    def test_unknown_option_and_bad_values(self):
        for body in ("[tree-li]\ndatta = x\n", "[tree-li]\nping_workers = lots\n",
                     "[tree-li]\nsession_log = maybe\n", "[other]\n", "[tree-li]\nuser = -oProxyCommand=x\n"):
            conf = self.write("bad.conf", body)
            with self.assertRaises(tl.ConfigError, msg=body):
                tl.load_config(args(config=conf))


class TestSearchSort(unittest.TestCase):
    def devices(self, rows):
        out = []
        for name, ip in rows:
            d = tl.Device()
            d.values, d.host, d.name, d.cells = {}, ip, name, [name, ip]
            d.search = "\x00".join(d.cells).lower()
            out.append(d)
        return out

    def test_filter_tokens_all_must_match(self):
        ds = self.devices([("ber-core-01", "10.0.0.1"), ("ber-acc-01", "10.0.0.2"), ("muc-core-01", "10.0.1.1")])
        self.assertEqual([d.name for d in tl.filter_devices(ds, "core BER")], ["ber-core-01"])
        self.assertEqual(len(tl.filter_devices(ds, "  ")), 3)
        # tokens never match across two fields
        self.assertEqual(tl.filter_devices(ds, "01 10"), ds)
        self.assertEqual(tl.filter_devices(ds, "0110"), [])

    def test_natural_sort_and_empty_last(self):
        ds = self.devices([("sw10", "10.0.0.10"), ("", "10.0.0.9"), ("sw2", "10.0.0.2")])
        self.assertEqual([d.name for d in tl.sort_devices(ds, 0, False, {})], ["sw2", "sw10", ""])
        self.assertEqual([d.name for d in tl.sort_devices(ds, 0, True, {})], ["sw10", "sw2", ""])
        self.assertEqual([d.host for d in tl.sort_devices(ds, 1, False, {})],
                         ["10.0.0.2", "10.0.0.9", "10.0.0.10"])

    def test_sort_by_ping_down_first(self):
        ds = self.devices([("a", "1"), ("b", "2"), ("c", "3")])
        states = {"1": tl.PING_UP, "2": tl.PING_DOWN}
        self.assertEqual([d.name for d in tl.sort_devices(ds, 2, False, states)], ["b", "a", "c"])


class TestSecurityHelpers(unittest.TestCase):
    def test_valid_host(self):
        for ok in ("10.0.0.1", "sw1.example.com", "fe80::1%eth0", "SW_01"):
            self.assertTrue(tl.valid_host(ok), ok)
        for bad in ("", "-oProxyCommand=sh", "a b", "x;rm -rf /", "$(id)", "a\nb"):
            self.assertFalse(tl.valid_host(bad), bad)

    def test_valid_user(self):
        self.assertTrue(tl.valid_user("timmy.r"))
        for bad in ("", "-l", "a b", "a@b"):
            self.assertFalse(tl.valid_user(bad), bad)

    def test_password_prompt_detection(self):
        for p in ("Password:", "admin@10.0.0.1's password: ", "Enter Password : ", "PASSWORD:"):
            self.assertTrue(tl.is_password_prompt(p), p)
        for p in ("Enter passphrase for key '/home/u/.ssh/id_rsa': ", "Verification code:",
                  "password policy updated", "login:"):
            self.assertFalse(tl.is_password_prompt(p), p)

    def test_ssh_argv(self):
        cfg = tl.load_config(args())
        cfg.ssh_options = ["-o", "StrictHostKeyChecking=yes"]
        argv = tl.build_ssh_argv(cfg, "timmy", "10.0.0.1", inject_password=True)
        self.assertEqual(argv[:3], ["ssh", "-o", "StrictHostKeyChecking=yes"])   # user options first
        self.assertIn("NumberOfPasswordPrompts=1", argv)
        self.assertEqual(argv[-4:], ["-l", "timmy", "--", "10.0.0.1"])
        self.assertNotIn("NumberOfPasswordPrompts=1", tl.build_ssh_argv(cfg, "t", "h", inject_password=False))


class TestKeys(unittest.TestCase):
    def test_escape_sequences(self):
        cases = {"": "ESC", "[A": "UP", "OA": "UP", "[11~": "F1", "OP": "F1", "[[E": "F5",
                 "[17~": "F6", "[1;5A": "UP", "[15;2~": "F5", "[5~": "PGUP", "[Z": "BTAB", "[999~": None}
        for seq, key in cases.items():
            self.assertEqual(tl.parse_escape_sequence(seq), key, seq)


class TestDrawingHelpers(unittest.TestCase):
    def test_fit(self):
        self.assertEqual(tl.fit("abc", 5), "abc  ")
        self.assertEqual(tl.fit("abcdef", 4), "abc~")

    def test_fit_widths(self):
        self.assertEqual(sum(tl.fit_widths([40, 20, 6], 50)), 50)
        self.assertEqual(tl.fit_widths([10, 10], 50), [10, 10])

    def test_wrap(self):
        self.assertEqual(tl.wrap_lines(["a" * 25, ""], 10), ["a" * 10, "a" * 10, "a" * 5, ""])


class TestProcStream(unittest.TestCase):
    def test_stream_collects_output(self):
        s = tl.ProcStream([sys.executable, "-c", "print('hello'); print('world')"])
        for _ in range(100):
            if s.done:
                break
            import time
            time.sleep(0.05)
        self.assertTrue(s.done)
        self.assertEqual(s.returncode, 0)
        self.assertIn("hello", s.snapshot())
        self.assertIn("world", s.snapshot())

    def test_missing_binary(self):
        s = tl.ProcStream(["/nonexistent/binary"])
        self.assertTrue(s.done)
        self.assertEqual(s.returncode, 127)


if __name__ == "__main__":
    unittest.main()
