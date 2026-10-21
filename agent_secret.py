#!/usr/bin/env python3
"""agent_secret: give secrets to one command, not to your coding agent.

  python agent_secret.py run SUPABASE_URL,GROQ_API_KEY -- npm run dev
  python agent_secret.py names

Secrets live in a JSON or .env file whose path is in AGENT_SECRET_FILE
(or passed with --file). The agent only ever sees names. For each run:

- only the listed names are put into that one command's environment;
- every secret value is masked in the command's stdout/stderr;
- AI coding CLIs (claude, codex, gemini, ...) are refused, so they can't
  pick up a paid API key instead of your subscription;
- on Windows, .cmd/.bat targets with shell metacharacters are refused.

Standard library only. Python 3.8+. Windows, macOS, Linux.
"""
import json
import os
import shutil
import subprocess
import sys
import threading

FILE_VAR = "AGENT_SECRET_FILE"
MASK = "***"
ENGINES = {"claude", "codex", "agy", "gemini"}
LAUNCHERS = {"npx", "bunx"}
DLX = {"pnpm", "yarn"}
CMD_META = set('&|<>^%!"()')


def load(path):
    """Read a JSON object or a KEY=VALUE .env file into a dict."""
    if not path or not os.path.isfile(path):
        raise SystemExit(f"No secret file. Set {FILE_VAR} or pass --file.")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if text.lstrip().startswith("{"):
        data = json.loads(text)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.startswith("export "):
            k = k[7:].strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k] = v
    return out


def take(names, path=None):
    """Names -> {name: value}. Exits listing only the missing names."""
    data = load(path or os.environ.get(FILE_VAR, ""))
    out = {n: data[n] for n in names if n in data}
    data.clear()
    missing = [n for n in names if n not in out]
    if missing:
        raise SystemExit(f"Not in the secret file: {', '.join(missing)}")
    return out


def _masks(vals):
    m = {v for v in vals if len(v) >= 8}
    for v in list(m):
        m |= {x.strip() for x in v.splitlines() if len(x.strip()) >= 16}
    return sorted(m, key=len, reverse=True)


def _pump(src, dst, masks):
    bm = [m.encode("utf-8") for m in masks]
    mask = MASK.encode("utf-8")
    for line in iter(src.readline, b""):
        for m in bm:
            if m in line:
                line = line.replace(m, mask)
        try:
            dst.write(line)
            dst.flush()
        except (OSError, ValueError):
            pass
    src.close()


def _base(x):
    return os.path.splitext(os.path.basename(str(x)))[0].lower()


def engine_of(cmd):
    """Name of the AI CLI the command launches (also via npx/bunx/pnpm dlx/yarn dlx), else ''."""
    exe = _base(cmd[0])
    if exe in ENGINES:
        return exe
    rest = list(cmd[1:])
    if exe in DLX and rest[:1] == ["dlx"]:
        rest = rest[1:]
    elif exe not in LAUNCHERS:
        return ""
    for a in rest:
        if a.startswith("-"):
            continue
        name = ("@" + a[1:].split("@")[0]) if a.startswith("@") else a.split("@")[0]
        last = name.rsplit("/", 1)[-1].lower()
        if last in ENGINES or last.startswith(("claude-code", "codex", "gemini-cli")):
            return last
        return ""
    return ""


def cmd_unsafe(path, args):
    """cmd.exe re-parses arguments of .cmd/.bat files; refuse metacharacters there."""
    if os.path.splitext(str(path))[1].lower() not in (".cmd", ".bat"):
        return ""
    bad = [a for a in args if any(c in CMD_META for c in a) or "\n" in a or "\r" in a]
    if not bad:
        return ""
    return f"{os.path.basename(str(path))} runs through cmd.exe; argument {bad[0][:40]!r} has shell metacharacters."


def run(names, cmd, path=None, which=shutil.which):
    if not cmd:
        raise SystemExit("Put the command after `--`.")
    exe = engine_of(cmd)
    if exe:
        raise SystemExit(f"Refusing to pass secrets to {exe}.")
    target = which(cmd[0]) or cmd[0]
    why = cmd_unsafe(target, cmd[1:])
    if why:
        raise SystemExit(why)
    vals = take(names, path)
    env = {k: v for k, v in os.environ.items() if k != FILE_VAR}
    env.update(vals)
    masks = _masks(vals.values())
    try:
        p = subprocess.Popen([target] + cmd[1:], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise SystemExit(f"Could not start the command: {e}")
    finally:
        vals.clear()
        env.clear()
    out = getattr(sys.stdout, "buffer", sys.stdout)
    err = getattr(sys.stderr, "buffer", sys.stderr)
    t = threading.Thread(target=_pump, args=(p.stderr, err, masks), daemon=True)
    t.start()
    try:
        _pump(p.stdout, out, masks)
        code = p.wait()
    except KeyboardInterrupt:
        p.terminate()
        code = p.wait()
    t.join(timeout=5)
    masks.clear()
    return code


def main(argv):
    path = None
    if argv[:1] == ["--file"] and len(argv) >= 2:
        path, argv = argv[1], argv[2:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "names":
        print(", ".join(sorted(load(path or os.environ.get(FILE_VAR, "")))) or "(none)")
        return 0
    if argv[0] == "run" and len(argv) >= 3 and argv[2] == "--":
        names = [n.strip() for n in argv[1].split(",") if n.strip()]
        if not names or not all(n.replace("_", "a").isalnum() and not n[0].isdigit() for n in names):
            raise SystemExit("Names are letters, digits and underscores, comma-separated.")
        return run(names, argv[3:], path)
    raise SystemExit("Usage: agent_secret.py [--file PATH] run NAME[,NAME] -- command   |   names")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
