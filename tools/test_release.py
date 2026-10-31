"""Release test: build every edition with the patcher of each branch and check that the builds verify and match each other.
usage: python3 tools/test_release.py ISO_DIR [--us1 F --us2 F --dc1 F --dc2 F] [--branches main,patcher-fixes]
                                             [--editions regular,undub] [--no-single] [--work DIR]
  ISO_DIR holds us1.iso, us2.iso (SLUS-21041/21044) and dc1.iso, dc2.iso (SLPS-73214/73215); --usN/--dcN name other files.
  Each branch's sh2dc_patcher.py, patchdata.zip and pcmscodec are taken from git (the local branch, else origin/BRANCH), so the
  working tree may be on any branch.  Builds run one at a time in WORK/out and are deleted once hashed: about 13 GB free is
  enough with the single-disc build, 9 GB without.  Prints a summary at the end (also in WORK/summary.txt; the full patcher
  output is in WORK/test_release.log)."""
import argparse, hashlib, importlib.util, os, platform, re, shutil, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
EXPECTED = {"us1": "SLUS_210.41", "us2": "SLUS_210.44", "dc1": "SLPS_732.14", "dc2": "SLPS_732.15"}
NOTEWORTHY = re.compile(r"done|FAILED|check failed|WARNING|NOTE|resampled|differs|not enough|not found|NOT verified|deleted the unfinished")

def gb(n): return "%.2f GB" % (n / 1e9)

def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def disc_info(path):
    """'SLUS_210.41 VER 1.00 NTSC, 3.71 GB' from the disc's SYSTEM.CNF."""
    spec = importlib.util.spec_from_file_location("sh2dc_patcher", os.path.join(ROOT, "sh2dc_patcher.py"))
    P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)
    try:
        iso = P.Iso(path); cnf = iso.read_at(*iso.files["SYSTEM.CNF"]).decode("ascii", "replace"); iso.close()
    except (SystemExit, KeyError, OSError) as e: return None, "unreadable (%s)" % e
    field = lambda k: (re.search(r"^\s*%s\s*=\s*(.+?)\s*$" % k, cnf, re.M) or [None, "?"])[1]
    serial = re.split(r"[\\:;]", field("BOOT2"))[-2] if ";" in field("BOOT2") else field("BOOT2")
    return serial, "%s VER %s %s, %s" % (serial, field("VER"), field("VMODE"), gb(os.path.getsize(path)))

def git(*args): return subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, check=True).stdout

def checkout(branch, dst):
    """The release files of a branch into dst (sh2dc_patcher.py, patchdata.zip, pcmscodec)."""
    ref = next((r for r in (branch, "origin/" + branch)
                if subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "--quiet", r + "^{commit}"], capture_output=True).returncode == 0), None)
    if ref is None: raise SystemExit("branch %s not found; run: git fetch origin" % branch)
    os.makedirs(dst, exist_ok=True)
    for name in ("sh2dc_patcher.py", "patchdata.zip", "pcmscodec"):
        try: data = git("show", "%s:%s" % (ref, name))
        except subprocess.CalledProcessError: continue                     # a branch without the Linux codec
        open(os.path.join(dst, name), "wb").write(data)
    if os.path.exists(os.path.join(dst, "pcmscodec")): os.chmod(os.path.join(dst, "pcmscodec"), 0o755)
    return ref, git("rev-parse", "--short", ref).decode().strip()

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iso_dir", nargs="?", default=".")
    for k in EXPECTED: ap.add_argument("--" + k)
    ap.add_argument("--branches", default="main,patcher-fixes"); ap.add_argument("--editions", default="regular,undub")
    ap.add_argument("--no-single", action="store_true"); ap.add_argument("--work", default=os.path.join(ROOT, "test_out"))
    a = ap.parse_args()
    isos = {k: os.path.abspath(getattr(a, k) or os.path.join(a.iso_dir, k + ".iso")) for k in EXPECTED}
    missing = [p for p in isos.values() if not os.path.isfile(p)]
    if missing: raise SystemExit("not found: %s\nput the discs in ISO_DIR as us1.iso us2.iso dc1.iso dc2.iso, or name them with --us1 ..." % ", ".join(missing))
    branches, editions = a.branches.split(","), a.editions.split(",")
    modes = ["two-disc"] + ([] if a.no_single else ["single"])
    work, out = os.path.abspath(a.work), os.path.join(os.path.abspath(a.work), "out")
    os.makedirs(work, exist_ok=True); shutil.rmtree(out, ignore_errors=True)
    need = 13e9 if "single" in modes else 9e9; free = shutil.disk_usage(work).free
    if free < need: raise SystemExit("only %s free in %s; this test needs about %s" % (gb(free), work, gb(need)))

    S = []; say = lambda s="": (S.append(s), print(s, flush=True))
    try: import numpy; npv = numpy.__version__
    except ImportError: npv = "MISSING (UnDub resampling will be skipped)"
    try: import scipy; spv = scipy.__version__
    except ImportError: spv = "-"
    say("== sh2dc release test ==")
    say("system: %s, Python %s, numpy %s, scipy %s, %d threads, %s free" % (platform.platform(), platform.python_version(), npv, spv, os.cpu_count() or 1, gb(free)))
    say("inputs:")
    for k, p in isos.items():
        serial, info = disc_info(p)
        say("  %s %s%s" % (k, info, "" if serial == EXPECTED[k] else "   <- expected %s" % EXPECTED[k]))
    refs = {b: checkout(b, os.path.join(work, b)) for b in branches}
    say("branches: " + ", ".join("%s (%s)" % (b, refs[b][1]) for b in branches)); os.makedirs(out)

    runs = [(b, e, m) for b in branches for e in editions for m in modes]; results, hashes = [], {}
    log = open(os.path.join(work, "test_release.log"), "w")
    print("\n%d builds; each takes a few minutes, mostly copying ISOs\n" % len(runs), flush=True)
    try:
        for n, (b, e, m) in enumerate(runs, 1):
            print("[%d/%d] %s %s %s ..." % (n, len(runs), b, e, m), end=" ", flush=True)
            cmd = [sys.executable, "-u", os.path.join(work, b, "sh2dc_patcher.py"), "--edition", e, "--out", out]
            for k, p in isos.items(): cmd += ["--" + k, p]
            if m == "single": cmd.append("--single-disc")
            t = time.monotonic(); r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True); dt = time.monotonic() - t
            log.write("\n===== %s %s %s: exit %d, %.0f s\n%s" % (b, e, m, r.returncode, dt, r.stdout)); log.flush()
            files = sorted(os.listdir(out)); isofiles = [f for f in files if f.endswith(".iso") and not f.startswith("~")]
            for f in isofiles: hashes[(e, m, f, b)] = (md5_file(os.path.join(out, f)), os.path.getsize(os.path.join(out, f)))
            lines = [l.strip().replace(out + os.sep, "") for l in r.stdout.splitlines() if l.strip()]
            notes = [l for l in lines if NOTEWORTHY.search(l)]
            if r.returncode: notes += [l for l in lines[-3:] if l not in notes]
            ok = r.returncode == 0 and isofiles and not any("FAILED" in l or "check failed" in l for l in notes)
            results.append((b, e, m, ok, dt, notes, [f for f in files if f not in isofiles]))
            print("%s (%dm%02ds)" % ("ok" if ok else "FAILED", dt // 60, dt % 60), flush=True)
            for f in files: os.remove(os.path.join(out, f))
    except KeyboardInterrupt:
        say("\nstopped (Ctrl+C)")
    finally:
        log.close(); shutil.rmtree(out, ignore_errors=True)

    say("\nruns:")
    for b, e, m, ok, dt, notes, left in results:
        say("  %-14s %-7s %-8s %-6s %dm%02ds" % (b, e, m, "ok" if ok else "FAILED", dt // 60, dt % 60))
        for l in notes: say("      " + l)
        if left: say("      left behind in the output folder: " + ", ".join(left))
    say("\noutputs (md5):")
    same = differ = 0
    for e, m, f in sorted({k[:3] for k in hashes}):
        got = {b: hashes.get((e, m, f, b)) for b in branches}
        say("  %s %s: %s" % (e, m, f))
        for b in branches: say("      %-14s %s" % (b, "%s  %s" % (got[b][0], gb(got[b][1])) if got[b] else "-"))
        if all(got.values()) and len({v[0] for v in got.values()}) == 1: same += 1
        else: differ += 1
    failed = sum(not r[3] for r in results); differ = differ if len(branches) > 1 else 0
    say("\nresult: %d of %d builds ok" % (len(results) - failed, len(runs)) + ("" if len(branches) < 2 else
        "; the branches give identical ISOs (%d of %d)" % (same, same) if not differ else "; %d ISOs differ between the branches or are missing" % differ))
    open(os.path.join(work, "summary.txt"), "w").write("\n".join(S) + "\n")
    print("\nsummary: %s\nfull log: %s" % (os.path.join(work, "summary.txt"), os.path.join(work, "test_release.log")))
    sys.exit(1 if failed or differ or len(results) < len(runs) else 0)

if __name__ == "__main__":
    main()
