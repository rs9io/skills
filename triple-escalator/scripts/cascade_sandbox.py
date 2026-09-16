"""macOS coding-worker filesystem and network boundary. Fail closed elsewhere."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def profile(repo, runtime, executable, ports, read_dirs=()):
    if sys.platform != "darwin" or not Path('/usr/bin/sandbox-exec').exists():
        raise ValueError("Coding workers currently require macOS sandbox-exec; no unsandboxed fallback.")
    repo, runtime = Path(repo).resolve(), Path(runtime).resolve()
    read = {Path(p) for p in ['/System', '/usr', '/bin', '/sbin', '/Library', '/opt/homebrew', '/dev', '/private/var/db/timezone']}
    read.update([repo, runtime, Path(executable).resolve().parent.parent])
    # Existing language runtimes may be symlinked from ~/.local/bin.
    for name in ['node', 'bun', 'python3', 'git', 'rg']:
        target = shutil.which(name)
        if target:
            read.add(Path(target).resolve().parent.parent)
    for directory in read_dirs:
        path = Path(directory).expanduser().resolve()
        if path in (Path('/'), Path.home()) or not path.is_dir():
            raise ValueError("Extra reads must name a specific existing dependency directory.")
        read.add(path)
    git_dir = Path(subprocess.check_output(['git','-C',str(repo),'rev-parse','--path-format=absolute','--git-common-dir'],text=True).strip())
    write = {repo, runtime, git_dir}
    read.add(git_dir)
    q = lambda p: json.dumps(str(p))
    rule = lambda roots: ' '.join('(subpath '+q(p)+')' for p in sorted(roots))
    return '\n'.join([
        '(version 1)', '(allow default)',
        '(deny file-read* file-write* network* signal)',
        '(allow signal (target same-sandbox))',
        '(allow file-read-metadata)',
        '(allow file-read* '+rule(read)+')',
        '(allow file-read* (literal "/") (literal "/private") (literal "/private/etc") (subpath "/private/etc/ssl") (literal "/private/etc/localtime"))',
        '(allow file-write* '+rule(write)+' (literal "/dev/null") (literal "/dev/tty"))',
        '(deny file-write* (subpath '+q(git_dir/'hooks')+') (literal '+q(git_dir/'config')+'))',
        # Denies apply even if a file is under an otherwise allowed checkout.
        '(deny file-read* file-write* (regex #"(^|/)[.]env($|[./])") (regex #"(^|/)(credentials|id_rsa|id_ed25519)($|[./])") )',
        '(allow network-bind network-inbound (local tcp "localhost:*"))',
        '(allow network-outbound '+' '.join('(remote tcp "localhost:'+str(p)+'")' for p in ports)+')',
    ])
