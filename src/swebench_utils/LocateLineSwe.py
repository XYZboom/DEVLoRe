import os
import traceback
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv, find_dotenv

from src.common_utils import record_error_stack
from src.swebench_utils.swebench_utils import raw_data, swe_pids_bids

_ = load_dotenv(find_dotenv())
SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
MODULE_NAME = os.environ.get("MODULE_NAME", "gpt-4o-mini")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))

LocateMethodPrompt = """Review the following skeleton of classes, test case(s), 
and exception that occurs when doing the test.
Provide a set of locations that need to be edited to fix the issue. 
The locations must be specified as line numbers.
### Skeleton of Classes ###
{skeleton_of_classes}
### Failed Test(s) ###
{failed_tests}{stack_info}{issue_content}
### Buggy Methods (for your reference only) ###
{buggy_methods}

Please provide line numbers that need to be edited.
### Examples:
```
path/to/file1.py ---- 123
path/to/file1.py ---- 215
path/to/file2.py ---- 316
```
```
path/to/file1.py ---- 316
path/to/file2.py ---- 251
```
Return just the location(s)
"""

SYS_PROMPT = "You are a software development engineer"

if __name__ == '__main__':
    from src import Chat
    import json
    import argparse
    import concurrent.futures

    parser = argparse.ArgumentParser()
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    parser.add_argument("--add-stack-info", help="add stack info", default=False)
    parser.add_argument("--dry-run", default=False)
    args = parser.parse_args()
    _add_issue = args.add_issue_info
    _add_stack = args.add_stack_info
    _dry_run = args.dry_run

    if _add_stack:
        if _add_issue:
            _output_path = f"{OUTPUT_PATH}/LocateLineIssueStack"
            _buggy_method_path = Path(OUTPUT_PATH) / 'LocateMethodIssueStack'
        else:
            _output_path = f"{OUTPUT_PATH}/LocateLineStack"
            _buggy_method_path = Path(OUTPUT_PATH) / 'LocateMethodStack'
    elif _add_issue:
        _output_path = f"{OUTPUT_PATH}/LocateLineIssue"
        _buggy_method_path = Path(OUTPUT_PATH) / 'LocateMethodIssue'
    else:
        _output_path = f"{OUTPUT_PATH}/LocateLine"
        _buggy_method_path = Path(OUTPUT_PATH) / 'LocateMethod'

    if not os.path.exists(_output_path):
        os.makedirs(_output_path)


    @record_error_stack
    def do_extract(pid, bid):
        if os.path.exists(f"{_output_path}/{pid}_{bid}b.json"):
            print(f"{pid}_{bid}b exists.")
            return
        _prefix = str(Path(SWEBENCH_LITE_PREPARE_PATH) / 'bugs' / f'{pid}_{bid}b')
        _failed_test_path = f"{SWEBENCH_LITE_PREPARE_PATH}/failed_test_content/{pid}_{bid}b.json"
        _skeleton_path = f"{SWEBENCH_LITE_PREPARE_PATH}/related_methods_skeleton/{pid}_{bid}b.json"
        _stack_path = f"{SWEBENCH_LITE_PREPARE_PATH}/failed_test_stacktrace/{pid}_{bid}b.txt"
        if not os.path.exists(_skeleton_path) or not os.path.exists(_buggy_method_path):
            print(f"not enough info for {pid}_{bid}b")
            return
        print(f"start {pid}_{bid}b")
        with open(_buggy_method_path / f'{pid}_{bid}b.json') as _f:
            _buggy_data = json.load(_f)
        chat = Chat.Chat(MODULE_NAME, SYS_PROMPT)
        with open(_skeleton_path, mode="r") as _f:
            _skeleton: Dict[str, Any] = json.load(_f)

        def _buggy_method_in_this_file(__file_content: str):
            __methods = _buggy_data['response'].split('\n')
            for __method in __methods:
                if __method in __file_content:
                    return True
            return False

        _skeleton_of_classes = "\n".join([
            f"### {_file_name.replace(_prefix, '').removeprefix('/')} ###\n{_skeleton[_file_name]}"
            for _file_name in _skeleton if _buggy_method_in_this_file(_skeleton[_file_name])
        ])

        with open(_failed_test_path, mode="r") as _f:
            _failed_test = json.load(_f)

        def join_methods(methods):
            return "\n".join([
                f"#### {_method_name} ####\n{methods[_method_name]}"
                for _method_name in methods
            ])

        _failed_test = "\n".join([
            f"### {_file_name} ###\n{join_methods(_failed_test[_file_name])}"
            for _file_name in _failed_test
        ])

        if _add_issue:
            # noinspection PyBroadException
            try:
                issue_content = "\n### issue info ###\n"
                issue_content += raw_data(pid, bid)['problem_statement']
            except:
                issue_content = ""
        else:
            issue_content = ""
        if _add_stack:
            _stack_info = "\n### Stack Trace in Failed Test Case(s) ###\n"
            _stack_info += open(_stack_path, 'r').read()
            if not _stack_info:
                print(f"no failed test in {pid}_{bid}b")
                return
        else:
            _stack_info = ""
        user_prompt = LocateMethodPrompt.format(
            skeleton_of_classes=_skeleton_of_classes,
            failed_tests=_failed_test,
            stack_info=_stack_info,
            issue_content=issue_content,
            buggy_methods=_buggy_data['response']
        )
        if not _dry_run:
            try:
                message = chat.chat(user_prompt)
            except Exception as e:
                traceback.print_exc()
                return
            _result = {
                "system_prompt": SYS_PROMPT,
                "user_prompt": user_prompt,
                "response": message,
            }
            print(f"finish chat in {pid}_{bid}b")
            with open(f"{_output_path}/{pid}_{bid}b.json", "w") as _f:
                json.dump(_result, _f)
        else:
            print(user_prompt)


    # for pid, bid in swe_pids_bids():
    #     if pid not in ['django']:
    #         continue
    #     do_extract(pid, bid)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=64
    ) as executor:
        futures = [
            executor.submit(
                do_extract,
                pid,
                bid
            )
            for pid, bid in swe_pids_bids()
        ]
        concurrent.futures.wait(futures)
