import os
import re
from collections import defaultdict
from typing import Iterable

from dotenv import load_dotenv, find_dotenv

from src.git_utils.git_utils import git_clone

_ = load_dotenv(find_dotenv())
SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
TEMP_PATH = os.environ.get("TMPDIR")

from datasets import load_dataset

__ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

__all_pids = set(map(lambda data: data['repo'].split('/')[-1], __ds))
__pid_data_dict = defaultdict(list)
for __data in __ds:
    __pid_data_dict[__data['repo'].split('/')[-1]].append(__data)


def prepare_swebench_lite_repos():
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    repos = set(map(lambda data: data['repo'], ds))
    for repo in repos:
        clone_to = f"{SWEBENCH_LITE_PREPARE_PATH}/repos/{repo.split('/')[-1]}"
        if os.path.exists(clone_to):
            print(f"{clone_to} already exists")
            continue
        git_clone(f"https://github.com/{repo}", clone_to)


def all_project_ids() -> Iterable[str]:
    return __all_pids


def bug_ids(_pid) -> Iterable[int]:
    return range(len(__pid_data_dict[_pid]))


def swe_pids_bids():
    all_pids = all_project_ids()
    for _pid in all_pids:
        all_bids = bug_ids(_pid)
        for _bid in all_bids:
            yield _pid, _bid


__django_test_reg = re.compile(r"([a-zA-Z0-9._]+) \(([a-zA-Z0-9._]+)\)$")


def swe_failed_test(_pid: str, _bid: int):
    __r = eval(__pid_data_dict[_pid][_bid]['FAIL_TO_PASS'])
    if _pid == 'django':
        __new_r = []
        for _name in __r:
            match = re.search(__django_test_reg, _name)
            if match:
                __new_r.append(f'{match.group(2)}.{match.group(1)}')
        __r = __new_r
    return __r


def docker_id(_pid: str, _bid: int) -> str:
    return raw_data(_pid, _bid)['instance_id']


def raw_data(_pid: str, _bid: int):
    return __pid_data_dict[_pid][_bid]


if __name__ == '__main__':
    print()
