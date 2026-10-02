"""Unit tests for the logic in tree-li (stdlib unittest only).

Run from the repository root:  python3 -m unittest discover -s tests -v
"""
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
import time
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader = importlib.machinery.SourceFileLoader("treeli", os.path.join(ROOT, "tree-li"))
_spec = importlib.util.spec_from_loader("treeli", _loader)
tl = importlib.util.module_from_spec(_spec)
_loader.exec_module(tl)


def args(**kw):
    base = dict(config=None, data=None, user=None, log=False, check=False, ascii=False)
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
            d.lcells = [c.lower() for c in d.cells]
            d.search = "\x00".join(d.lcells)
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

    def test_sort_key_cycle_and_off(self):
        state = (None, False)
        seen = []
        for _ in range(4):
            state = tl.next_sort(state[0], state[1], 2)
            seen.append(state)
        self.assertEqual(seen, [(2, False), (2, True), (None, False), (2, False)])
        self.assertEqual(tl.next_sort(2, True, 0), (0, False))           # other column: ascending

    def test_tab_cycles_through_off(self):
        self.assertEqual([tl.cycle_sort(c, 3, 1) for c in (None, 0, 1, 2)], [0, 1, 2, None])
        self.assertEqual([tl.cycle_sort(c, 3, -1) for c in (None, 0, 2)], [2, None, 1])

    def test_sort_off_restores_csv_order(self):
        ds = self.devices([("sw10", "1"), ("sw2", "2"), ("sw1", "3")])
        sorted_once = tl.sort_devices(ds, 0, False, {})
        self.assertEqual([d.name for d in tl.sort_devices(ds, None, False, {})], ["sw10", "sw2", "sw1"])
        self.assertNotEqual(sorted_once, ds)

    def test_sort_by_ping_down_first(self):
        ds = self.devices([("a", "1"), ("b", "2"), ("c", "3")])
        states = {"1": tl.PING_UP, "2": tl.PING_DOWN}
        self.assertEqual([d.name for d in tl.sort_devices(ds, 2, False, [states, {}])], ["b", "a", "c"])
        ssh = {"1": tl.SSH_OPEN, "3": tl.SSH_CLOSED}
        self.assertEqual([d.name for d in tl.sort_devices(ds, 3, False, [states, ssh])], ["c", "a", "b"])


class TestSearchSyntax(unittest.TestCase):
    def setUp(self):
        headers = ["Name", "IP", "type", "aliases", "location"]
        rows = [dict(zip(headers, r)) for r in (
            ("ber-core-01", "10.0.0.1", "core", "Core Berlin", "Room 1"),
            ("ber-edge-01", "10.0.0.2", "edge", "Edge Berlin", ""),
            ("muc-core-01", "fe80::1", "core", "Core Munich", "Room 9"),
            ("ber-test-01", "10.0.0.4", "edge", "Test", "Lab"))]
        cfg = types.SimpleNamespace(host_column="IP", name_column="Name",
                                    columns=[("Name", "Name"), ("IP", "IP"), ("aliases", "Alias")])
        self.devices, columns, _ = tl.build_devices(headers, rows, cfg)
        self.fields = dict((h.lower(), h) for h in headers)
        self.fields.update((label.lower(), h) for h, label in columns)

    def names(self, query, **kw):
        return [d.name for d in tl.filter_devices(self.devices, query, self.fields, **kw)]

    def test_field_hidden_column_and_label(self):
        self.assertEqual(self.names("type:core"), ["ber-core-01", "muc-core-01"])
        self.assertEqual(self.names("TYPE:CORE ber"), ["ber-core-01"])
        self.assertEqual(self.names("alias:munich"), ["muc-core-01"])        # table label works too
        self.assertEqual(self.names("location:"), ["ber-edge-01"])             # empty column

    def test_negation(self):
        self.assertEqual(self.names("ber -test"), ["ber-core-01", "ber-edge-01"])
        self.assertEqual(self.names("-type:edge"), ["ber-core-01", "muc-core-01"])

    def test_unknown_field_is_plain_text(self):
        self.assertEqual(self.names("fe80::1"), ["muc-core-01"])                # IPv6 is not a field
        self.assertEqual(self.names("nosuch:x"), [])

    def test_ping_and_user_state(self):
        ping = {"status": {"ping": {"10.0.0.1": tl.PING_UP, "10.0.0.2": tl.PING_DOWN}}}
        self.assertEqual(self.names("ping:down", **ping), ["ber-edge-01"])
        self.assertEqual(self.names("ping:none", **ping), ["muc-core-01", "ber-test-01"])
        self.assertEqual(self.names("-ping:up", **ping), ["ber-edge-01", "muc-core-01", "ber-test-01"])
        ssh = {"status": {"ssh": {"10.0.0.1": tl.SSH_OPEN, "10.0.0.2": tl.SSH_SILENT}}}
        self.assertEqual(self.names("ssh:no", **ssh), ["ber-edge-01"])         # "no answer", not "none"
        self.assertEqual(self.names("ssh:none", **ssh), ["muc-core-01", "ber-test-01"])
        self.assertEqual(self.names("is:fav", favorites={"ber-test-01"}), ["ber-test-01"])
        self.assertEqual(self.names("is:recent", recent={"muc-core-01": 5}), ["muc-core-01"])
        self.assertEqual(self.names("is:favs", favorites={"ber-test-01"}), [])  # no hidden aliases
        self.assertEqual(self.names("ping:wait", status={"ping": {"10.0.0.4": tl.WAIT}}), ["ber-test-01"])

    def test_fuzzy_and_exact(self):
        self.assertEqual(self.names("bc01"), ["ber-core-01"])                  # b..c..01 in order
        self.assertEqual(self.names("bt"), ["ber-test-01"])                    # b..t only in ber-test-01
        self.assertEqual(self.names("'bc01"), [])                              # exact: not a substring
        self.assertEqual(self.names("'core ber"), ["ber-core-01"])
        self.assertEqual(self.names("-tst"), self.names(""))                   # excludes are exact

    def test_fuzzy_ranking_and_marks(self):
        found = {}
        view = tl.filter_devices(self.devices, "core", self.fields, found=found)
        order = [d.name for d in tl.default_order(view, "core", set(), {}, found)]
        self.assertEqual(order, ["ber-core-01", "muc-core-01"])
        d = next(d for d in view if d.name == "ber-core-01")
        self.assertEqual(found[d][1], {0: {4, 5, 6, 7}})                      # "core" in the Name column

    def test_default_order(self):
        favorites, recent = {"muc-core-01"}, {"ber-edge-01": 10, "ber-test-01": 20}
        order = [d.name for d in tl.default_order(self.devices, "", favorites, recent)]
        self.assertEqual(order[0], "muc-core-01")                              # favourites pinned
        order = [d.name for d in tl.default_order(self.devices, "is:recent", favorites, recent)]
        self.assertEqual(order[:2], ["ber-test-01", "ber-edge-01"])            # newest first


class TestFuzzyMatch(unittest.TestCase):
    def test_match_and_positions(self):
        self.assertEqual(tl.fuzzy_match("bc01", "ber-core-01")[1], (0, 4, 9, 10))
        self.assertIsNone(tl.fuzzy_match("cb", "ber-core-01"))                 # order matters
        self.assertEqual(tl.fuzzy_match("core", "ber-core-01")[1], (4, 5, 6, 7))

    def test_scores(self):
        exact = tl.fuzzy_match("core", "ber-core-01")[0]
        scattered = tl.fuzzy_match("cr01", "ber-core-01")[0]
        boundary = tl.fuzzy_match("bc", "ber-core-01")[0]
        middle = tl.fuzzy_match("ro", "ber-core-01")[0]
        self.assertGreater(exact, scattered)                                   # substring always wins
        self.assertGreater(boundary, middle)                                   # word starts score higher


class TestUserState(TempDir):
    def test_favorites_and_recent_persist(self):
        st = tl.UserState(os.path.join(self.tmp, "state"))
        self.assertTrue(st.toggle_favorite("sw1"))
        st.touch("sw2")
        again = tl.UserState(os.path.join(self.tmp, "state"))
        self.assertEqual(again.favorites, {"sw1"})
        self.assertIn("sw2", again.recent)
        self.assertFalse(again.toggle_favorite("sw1"))
        self.assertEqual(tl.UserState(os.path.join(self.tmp, "state")).favorites, set())
        mode = os.stat(os.path.join(self.tmp, "state", "favorites")).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_history_is_trimmed_and_tolerates_garbage(self):
        d = os.path.join(self.tmp, "state")
        os.makedirs(d)
        with open(os.path.join(d, "recent"), "w") as f:
            f.write("garbage\nnot-a-number\tsw9\n100\tsw1\n")
        self.assertEqual(tl.UserState(d).recent, {"sw1": 100.0})
        with open(os.path.join(d, "recent"), "w") as f:
            f.write("".join("%d\tx%d\n" % (i, i) for i in range(tl.UserState.MAX_RECENT + 20)))
        tl.UserState(d).touch("newest")
        self.assertEqual(len(tl.UserState(d).recent), tl.UserState.MAX_RECENT)
        self.assertIn("newest", tl.UserState(d).recent)

    def test_unwritable_directory_reports_error(self):
        blocker = os.path.join(self.tmp, "file")
        open(blocker, "w").close()
        st = tl.UserState(os.path.join(blocker, "state"))     # a file is in the way
        st.toggle_favorite("sw1")
        self.assertIsNotNone(st.error)
        self.assertEqual(st.favorites, {"sw1"})               # still works in memory


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


class TestCharset(TempDir):
    def test_setting_and_flag(self):
        self.assertEqual(tl.detect_charset("ascii"), "ascii")
        self.assertEqual(tl.detect_charset("unicode"), "unicode")
        self.assertIn(tl.detect_charset("auto"), ("ascii", "unicode"))
        self.assertEqual(tl.load_config(args(ascii=True)).charset_setting, "ascii")
        with self.assertRaises(tl.ConfigError):
            tl.load_config(args(config=self.write("c.conf", "[tree-li]\ncharset = emoji\n")))

    def test_symbol_sets_match(self):
        self.assertEqual(set(tl.CHARSETS["ascii"]), set(tl.CHARSETS["unicode"]))
        for value in tl.CHARSETS["ascii"].values():
            value.encode("ascii")
        self.assertEqual(len(tl.CHARSETS["unicode"]["box"]), 6)


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
        self.assertEqual(tl.fit("abcdef", 4, "\u2026"), "abc\u2026")

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
