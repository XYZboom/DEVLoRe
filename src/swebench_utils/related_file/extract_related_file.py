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
    _extract_path = os.path.join(SWEBENCH_LITE_PREPARE_PATH, 'related_files', f'{_pid}_{_bid}b.txt')
    if os.path.exists(_extract_path):
        print(f'{_pid}_{_bid} related files are already extracted')
        return
    _venv_py = f'{_path}_venv/bin/python'
    if _pid not in ['django', 'seaborn', 'matplotlib']:
        print(f'does not support {_pid}')
        return
    if _pid == 'django':
        _ori_argv = sys.argv
        _test_script = os.path.join(_path, 'tests/runtests.py')
        _failed_tests = swe_failed_test(_pid, _bid)
        if not _failed_tests:
            return
        subprocess.run(
            [_venv_py, os.path.abspath(os.path.join(__file__, os.path.pardir, 'do_extract_related_file_django.py')),
             _test_script, _extract_path,
             "-f", _path, os.path.join(TEMP_PATH, f'{_pid}_{_bid}b'),
             "-args", *_failed_tests])
    elif _pid == 'seaborn' or _pid == 'matplotlib':
        _ori_argv = sys.argv
        _test_script = os.path.join(os.path.dirname(_venv_py), 'pytest')
        _failed_tests = swe_failed_test(_pid, _bid)
        if not _failed_tests:
            return
        subprocess.run(
            [_venv_py, os.path.abspath(os.path.join(__file__, os.path.pardir, 'do_extract_related_file_in_pytest.py')),
             _test_script, _path, _extract_path,
             "-f", _path, os.path.join(TEMP_PATH, f'{_pid}_{_bid}b'),
             "-args", *_failed_tests])


if __name__ == '__main__':
    # for pid, bid in swe_pids_bids():
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
