import concurrent.futures
import os
import subprocess
import sys

from dotenv import load_dotenv, find_dotenv

from src.swebench_utils.swebench_utils import swe_pids_bids, swe_failed_test

_ = load_dotenv(find_dotenv())

SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
TEMP_PATH = os.environ.get("TMPDIR")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))


def __do_extract(_pid, _bid):
    _path = os.path.join(SWEBENCH_LITE_PREPARE_PATH, f'bugs/{_pid}_{_bid}b')
    _extract_path = os.path.join(SWEBENCH_LITE_PREPARE_PATH, 'related_files')
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
            [_venv_py, os.path.abspath(os.path.join(__file__, os.path.pardir, 'do_extract_related_file_django.py')),
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
