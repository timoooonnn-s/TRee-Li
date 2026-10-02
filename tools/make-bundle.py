#!/usr/bin/env python3
"""Pack TRee-Li into ONE self-extracting text file, e.g. to send it by mail.

    python3 tools/make-bundle.py            ->  dist/tree-li-bundle-<version>.py

On the target machine:

    python3 tree-li-bundle-<version>.py               # unpacks into ./tree-li
    python3 tree-li-bundle-<version>.py /srv/tree-li  # or into a directory of your choice
    python3 tree-li-bundle-<version>.py --list        # only show what is inside

The bundle is plain ASCII (the files are a base64-encoded tar.gz), carries a SHA-256
checksum so a damaged attachment is detected, and never contains or overwrites
site files such as data.csv or tree-li.conf - it can also be used to update.
Python 3.8+, standard library only.
"""

import base64
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Never shipped, even if present: site data, local settings, build output, caches.
EXCLUDE = re.compile(r"(^|/)(data\.csv|tree-li\.conf|dist|\.git|__pycache__|\.DS_Store)(/|$)|\.pyc$|\.log$")

EXTRACTOR = r'''#!/usr/bin/env python3
"""TRee-Li %(version)s - self-extracting bundle, created %(created)s.

    python3 %(name)s [TARGET_DIR]   unpack (default: ./tree-li); also updates an existing copy
    python3 %(name)s --list         show the contents only

Your data.csv and tree-li.conf are never part of the bundle and are never touched.
"""
import base64, hashlib, io, os, sys, tarfile

SHA256 = "%(sha256)s"
PAYLOAD = """
%(payload)s
"""


def main(argv):
    raw = base64.b64decode("".join(PAYLOAD.split()))
    if hashlib.sha256(raw).hexdigest() != SHA256:
        sys.exit("ERROR: the bundle is damaged (checksum mismatch) - please send it again.")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        members = tar.getmembers()
        for m in members:                   # only plain files with safe, relative names
            if not m.isfile() or m.name.startswith("/") or ".." in m.name.split("/"):
                sys.exit("ERROR: unexpected entry %%r in the bundle - not extracting." %% m.name)
        if argv[1:2] == ["--list"]:
            for m in members:
                print("%%8d  %%s" %% (m.size, m.name))
            return
        target = os.path.abspath(argv[1] if len(argv) > 1 else "tree-li")
        for m in members:
            path = os.path.join(target, *m.name.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            updated = os.path.exists(path)
            with open(path, "wb") as out:
                out.write(tar.extractfile(m).read())
            os.chmod(path, 0o755 if m.mode & 0o111 else 0o644)
            print("  %%s %%s" %% ("updated" if updated else "created", m.name))
    print("\nTRee-Li %(version)s is in %%s" %% target)
    if not os.path.exists(os.path.join(target, "data.csv")):
        print("Next:  cd %%s && cp data.example.csv data.csv   (then add your switches)" %% target)
    print("Check: %%s --check" %% os.path.join(target, "tree-li"))


if __name__ == "__main__":
    main(sys.argv)
'''


def project_files():
    """Files under version control plus new, not ignored ones; without git: everything."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        names = [n for n in out.decode("utf-8").split("\0") if n]
    except (OSError, subprocess.CalledProcessError):
        names = []
        for base, dirs, files in os.walk(ROOT):
            for f in files:
                names.append(os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, "/"))
    return sorted(n for n in names if not EXCLUDE.search(n) and os.path.isfile(os.path.join(ROOT, n)))


def version():
    with open(os.path.join(ROOT, "tree-li"), encoding="utf-8") as f:
        m = re.search(r'^VERSION = "([^"]+)"', f.read(), re.MULTILINE)
    return m.group(1) if m else "dev"


def main():
    files = project_files()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in files:
            path = os.path.join(ROOT, name)
            info = tar.gettarinfo(path, arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
            with open(path, "rb") as f:
                tar.addfile(info, f)
    raw = buf.getvalue()
    payload = base64.b64encode(raw).decode("ascii")
    ver = version()
    name = "tree-li-bundle-%s.py" % ver
    text = EXTRACTOR % {
        "version": ver,
        "name": name,
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "payload": "\n".join(payload[i:i + 76] for i in range(0, len(payload), 76)),
    }
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", name)
    with open(out, "w", encoding="ascii", newline="\n") as f:
        f.write(text)
    print("%d files -> %s (%d KB)" % (len(files), os.path.relpath(out, ROOT), (len(text) + 1023) // 1024))
    print("SHA-256 of the contents: %s" % hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
