import shutil
import subprocess
import sys
import threading
import venv

import git
import os
import re

from dotenv import load_dotenv, find_dotenv

from src.common_utils import record_error_stack

_ = load_dotenv(find_dotenv())

from src.swebench_utils.swebench_utils import prepare_swebench_lite_repos, swe_pids_bids, swe_failed_test, raw_data
from src.cmd_utils.cmd_utils import run_cmd, run_cmd_no_popen

from datasets import load_dataset
import concurrent.futures

SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
TEMP_PATH = os.environ.get("TMPDIR")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))


def prepare_swebench_lite_error_stack():
    _error_stack_path = f'{SWEBENCH_LITE_PREPARE_PATH}/failed_test_stacktrace'
    if not os.path.exists(_error_stack_path):
        os.makedirs(_error_stack_path)

    @record_error_stack
    def __prepare_swebench_lite_error_stack(_pid, _bid):
        print(f"prepare_swebench_lite_error_stack for {_pid}_{_bid}")
        _path = f"{TEMP_PATH}/{_pid}_{_bid}b"
        _result_path = f"{_error_stack_path}/{_pid}_{_bid}b.txt"
        if os.path.exists(_result_path):
            print(f"error stack for {_pid}_{_bid} exists")
            return
        if _pid != 'django':
            return
        _venv_py = checkout(_pid, _bid, _path)
        if _pid == 'django':
            _failed_tests = swe_failed_test(_pid, _bid)
            print(f"ready to run test for {_pid}_{_bid}")
            if not _failed_tests:
                print(f"{_pid}_{_bid} failed test is empty", file=sys.stderr)
                return
            stdout, stderr = run_cmd([_venv_py, "./runtests.py", "-v=0", *_failed_tests], f'{_path}/tests')
            open(_result_path, 'w').write(
                stderr.replace(os.path.abspath(_path), '')
                .replace(os.path.abspath(os.path.join(_venv_py, os.path.pardir, os.path.pardir)), '')
                .replace(os.path.abspath(os.path.join(SWEBENCH_LITE_PREPARE_PATH, f'./bugs/{_pid}_{_bid}b')), '')
            )
        else:
            # todo other repos
            return

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                __prepare_swebench_lite_error_stack,
                pid,
                bid
            )
            for pid, bid in swe_pids_bids()
        ]
        concurrent.futures.wait(futures)


def checkout(_pid: str, _bid: int, _path: str) -> str:
    _bugs_path = f"{SWEBENCH_LITE_PREPARE_PATH}/bugs/{_pid}_{_bid}b"
    _venv_py = f"{SWEBENCH_LITE_PREPARE_PATH}/bugs/{_pid}_{_bid}b_venv"
    if not os.path.exists(_venv_py):
        __checkout(_pid, _bid, _bugs_path)
    shutil.copytree(_bugs_path, _path, dirs_exist_ok=True)
    return f"{_venv_py}/bin/python"


def __checkout(_pid: str, _bid: int, _path: str) -> str:  # returns venv python exe path
    if os.path.exists(_path):
        shutil.rmtree(_path)
    _venv_path = f'{_path}_venv'
    __repo_path = f"{SWEBENCH_LITE_PREPARE_PATH}/repos/{_pid}"
    print(f'checking out {_pid}_{_bid}')
    if os.path.exists(_venv_path):
        shutil.rmtree(_venv_path)
    if os.path.exists(_path):
        shutil.rmtree(_path)
    if not os.path.exists(__repo_path):
        prepare_swebench_lite_repos()
    shutil.copytree(__repo_path, _path)
    __my_data = raw_data(_pid, _bid)
    __repo = git.Repo(_path)
    __repo.git.checkout(__my_data['environment_setup_commit'])
    print(f'create venv for {_pid}_{_bid}')
    venv.create(_venv_path, with_pip=True, system_site_packages=True)
    print(f'venv created for {_pid}_{_bid}')
    if os.name == "nt":
        _venv_py_path = os.path.join(_venv_path, "Scripts", "python3")
    else:
        _venv_py_path = os.path.join(_venv_path, "bin", "python3")
    if os.path.exists(f'{_path}/requirements.txt'):
        subprocess.run([_venv_py_path, "-m", "pip", "install", "-r", f'{_path}/requirements.txt'], check=True)
    elif os.path.exists(f'{_path}/setup.py'):
        run_cmd_no_popen([_venv_py_path, "-m", "pip", "install", "-e", "."], cwd=_path)
        if _pid == 'django':
            run_cmd_no_popen([_venv_py_path, "-m", "pip", "install", "-r", "tests/requirements/py3.txt"],
                             cwd=_path)
    __repo.git.checkout(__my_data['base_commit'])
    _test_patch_path = f'{_path}/swebench_test.patch'
    _fix_patch_path = f'{_path}/swebench_fix.patch'
    open(_test_patch_path, 'w').write(__my_data['test_patch'])
    open(_fix_patch_path, 'w').write(__my_data['patch'])
    run_cmd(['git', "apply", _test_patch_path], cwd=_path)
    return _venv_path


def prepare_swebench_lite_venvs():
    @record_error_stack
    def __prepare_swebench_lite_venvs(_pid, _bid):
        if _pid != 'django':
            print(f'does not support {_pid}_{_bid} now')
            return
        _path = f"{SWEBENCH_LITE_PREPARE_PATH}/bugs/{_pid}_{_bid}b"
        if os.path.exists(_path):
            print(f'{_pid}, {_bid} venv exists')
            return
        __checkout(_pid, _bid, _path)

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                __prepare_swebench_lite_venvs,
                pid,
                bid
            )
            for pid, bid in swe_pids_bids()
        ]
        concurrent.futures.wait(futures)


if __name__ == '__main__':
    prepare_swebench_lite_repos()
    prepare_swebench_lite_venvs()
    prepare_swebench_lite_error_stack()
