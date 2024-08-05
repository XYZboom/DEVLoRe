import os
import subprocess

from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
TEMP_PATH = os.environ.get("TEMP_PATH")
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")
D4J_TRIGGER_KEY = "d4j.tests.trigger"


def all_project_ids():
    _process = subprocess.Popen([D4J_EXEC, "pids"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    return _out.decode().splitlines()


def bug_ids(_pid):
    _process = subprocess.Popen([D4J_EXEC, "bids", "-p", _pid],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    return _out.decode().splitlines()


def d4j_pids_bids():
    all_pids = all_project_ids()
    for _pid in all_pids:
        all_bids = bug_ids(_pid)
        for _bid in all_bids:
            yield _pid, _bid


def trigger_test_stacktrace(_pid, _bid):
    _projects_path = os.path.abspath(os.path.join(D4J_EXEC, f"../../projects/{_pid}"))
    if not os.path.exists(_projects_path):
        return None
    _test_file = os.path.join(_projects_path, f"trigger_tests/{_bid}")
    if not os.path.exists(_test_file):
        return None
    with open(_test_file, "r") as f:
        _stacktrace = f.read().splitlines()
    _result = []
    _skip_junit_stack = False
    for _line in _stacktrace:
        if _skip_junit_stack:
            if _line.startswith("---"):
                _skip_junit_stack = False
            else:
                continue
        if "(Native Method)" in _line:
            _skip_junit_stack = True
            continue
        _result.append(_line)
    return "\n".join(_result)


def checkout(_pid, _bid, _path, _print_stdout=False, _print_stderr=False):
    _process = subprocess.Popen([D4J_EXEC, "checkout", "-p", _pid, "-v", f"{_bid}b", "-w", _path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    if _print_stdout:
        print(_out.decode())
    if _err and _print_stderr:
        print(_err.decode())


__ori_d4j = {
    'Chart': list(range(1, 26 + 1)),
    'Cli': list(range(1, 5 + 1)) + list(range(7, 40 + 1)),
    'Closure': list(range(1, 62 + 1)) + list(range(64, 92 + 1)) + list(range(94, 176 + 1)),
    'Codec': list(range(1, 18 + 1)),
    'Collections': list(range(25, 28 + 1)),
    'Compress': list(range(1, 47 + 1)),
    'Csv': list(range(1, 16 + 1)),
    'Gson': list(range(1, 18 + 1)),
    'JacksonCore': list(range(1, 26 + 1)),
    'JacksonDatabind': list(range(1, 112 + 1)),
    'JacksonXml': list(range(1, 6 + 1)),
    'Jsoup': list(range(1, 93 + 1)),
    'JxPath': list(range(1, 22 + 1)),
    'Lang': [1] + list(range(3, 65 + 1)),
    'Math': list(range(1, 106 + 1)),
    'Mockito': list(range(1, 38 + 1)),
    'Time': list(range(1, 20 + 1)) + list(range(22, 27 + 1)),
}


def is_ori_d4j(_pid, _bid):
    if _pid in __ori_d4j:
        return int(_bid) in __ori_d4j[_pid]
    return False
