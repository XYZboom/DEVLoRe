import subprocess
import sys
from typing import List, Tuple


def run_cmd(args: List[str], cwd: str) -> Tuple[str, str]:
    _process = subprocess.Popen(args,
                                cwd=cwd,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    print(_out.decode())
    print(_err.decode(), file=sys.stderr)
    return _out.decode(), _err.decode()


def run_cmd_no_popen(args: List[str], cwd: str):
    subprocess.run(args, cwd=cwd)
