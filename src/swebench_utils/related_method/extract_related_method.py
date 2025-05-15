import concurrent.futures
import importlib
import os
import runpy
import subprocess
import sys

from dotenv import load_dotenv, find_dotenv

from src.swebench_utils.swebench_utils import swe_pids_bids, swe_failed_test

_ = load_dotenv(find_dotenv())

SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
TEMP_PATH = os.environ.get("TMPDIR")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))


class Trace:
    def __init__(self, _pid: str, _bid: int):
        self.__pid = _pid
        self.__bid = _bid
        self.__allow_file_paths = [
            os.path.join(SWEBENCH_LITE_PREPARE_PATH, f'bugs/{_pid}_{_bid}b'),
            os.path.join(TEMP_PATH, f'{_pid}_{_bid}b')
        ]

    def trace_calls(self, _frame, _event, _arg):
        if _event == 'call':
            # 获取调用的函数/方法名和所在文件
            code = _frame.f_code
            func_name = code.co_name
            filename = code.co_filename
            lineno = _frame.f_lineno
            allow_record = any(map(lambda _f_name: filename.startswith(_f_name), self.__allow_file_paths))
            print(filename)
            if allow_record:
                print(filename, lineno, func_name)
        return self.trace_calls


def __do_extract(_pid, _bid):
    _path = os.path.join(SWEBENCH_LITE_PREPARE_PATH, f'bugs/{_pid}_{_bid}b')
    _extract_path = os.path.join(SWEBENCH_LITE_PREPARE_PATH, 'result_skeleton')
    _venv_py = f'{_path}_venv/bin/python'
    if _pid != 'django':
        print(f'does not support {_pid}')
    if _pid == 'django':
        _ori_argv = sys.argv
        _test_script = os.path.join(_path, 'tests/runtests.py')
        _failed_tests = swe_failed_test(_pid, _bid)
        if not _failed_tests:
            return
        subprocess.run(
            [_venv_py, os.path.abspath(os.path.join(__file__, os.path.pardir, 'do_extract_related_method_django.py')),
             _test_script, os.path.join(_extract_path, f'{_pid}_{_bid}b.txt'),
             "-f", _path, os.path.join(TEMP_PATH, f'{_pid}_{_bid}b'),
             "-args", *_failed_tests])


if __name__ == '__main__':
    # for pid, bid in swe_pids_bids():
    #     if pid != 'django' or bid != 47:
    #         continue
    #     __do_extract(pid, bid)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                __do_extract,
                pid,
                bid
            )
            for pid, bid in swe_pids_bids()
        ]
        concurrent.futures.wait(futures)
