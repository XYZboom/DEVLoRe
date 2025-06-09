import os
import traceback
from io import StringIO
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

from src import Chat
from src.common_utils import record_error_stack
from src.swebench_utils.swebench_utils import raw_data, swe_pids_bids
from swebench.harness.constants import SWEbenchInstance
from swebench.harness.utils import load_swebench_dataset

_ = load_dotenv(find_dotenv())
SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
MODULE_NAME = os.environ.get("MODULE_NAME", "gpt-4o-mini")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))

LocateLinePrompt = """Review the following files, test case(s), 
and exception that occurs when doing the test.
Try to fix the bug.
### Skeleton of Files ###
{skeleton_of_files}{stack_info}
### Failed Tests ###
{failed_tests}
### Possible bug locations (for your reference only) ###
{possible_bug_locations}{debug_info}{issue_content}

Please generate *SEARCH/REPLACE* edits to fix the bug based on the info given above.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path
2. The start of search block: <<<<<<< SEARCH
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE

Here is an example:

```py
### path/to/file.py
<<<<<<< SEARCH
def foo():
    print('buggy')
=======
def foo():
    print('fixed')
>>>>>>> REPLACE
```

Wrap the *SEARCH/REPLACE* edit in blocks ```py...```. **Keep indent**.
"""

SYS_PROMPT = "You are a software development engineer"

if __name__ == '__main__':
    import json
    import argparse
    import concurrent.futures

    parser = argparse.ArgumentParser()
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    parser.add_argument("--add-stack-info", help="add stack info", default=False)
    parser.add_argument("--add-debug-info", help="add debug info", default=False)
    parser.add_argument("--dry-run", default=False)
    args = parser.parse_args()
    _add_issue = args.add_issue_info
    _add_stack = args.add_stack_info
    _add_debug = args.add_debug_info
    _dry_run = args.dry_run

    suffix = ""
    if _add_issue:
        suffix += "Issue"
    if _add_stack:
        suffix += "Stack"
    out_suffix = suffix
    if _add_debug:
        out_suffix += "Debug"
    _locate_file_path = Path(OUTPUT_PATH) / f"LocateFile{suffix}"
    _locate_method_path = Path(OUTPUT_PATH) / f"LocateMethod{suffix}"
    _locate_line_path = Path(OUTPUT_PATH) / f"LocateLine{out_suffix}"
    _output_path = Path(OUTPUT_PATH) / f"Repair{out_suffix}"
    _debug_info_path = Path(OUTPUT_PATH) / f"debug_info_{suffix}"

    if not os.path.exists(_output_path):
        os.makedirs(_output_path)

    @record_error_stack
    def do_extract(_instance: SWEbenchInstance):
        my_id = _instance['instance_id']
        if os.path.exists(_output_path / f"{my_id}.json"):
            print(f"{my_id} exists.")
            return
        _failed_test_path = f"{SWEBENCH_LITE_PREPARE_PATH}/failed_test_content/{my_id}.json"
        _skeleton_path = f"{SWEBENCH_LITE_PREPARE_PATH}/related_methods/{my_id}.json"
        _method_content_path = f"{SWEBENCH_LITE_PREPARE_PATH}/related_method_content/{my_id}.json"
        _stack_path = f"{SWEBENCH_LITE_PREPARE_PATH}/failed_test_stacktrace/{my_id}.txt"
        locate_file_path = _locate_file_path / f'{my_id}.json'
        locate_line_path = _locate_line_path / f'{my_id}.json'
        debug_info_path = _debug_info_path / f'{my_id}.json'
        if not os.path.exists(_failed_test_path) or not os.path.exists(_skeleton_path) \
                or not os.path.exists(locate_file_path) \
                or not os.path.exists(locate_line_path) \
                or (_add_debug and not os.path.exists(debug_info_path)) \
                or (_add_stack and not os.path.exists(_stack_path)):
            print(f"not enough info for {my_id}")
            return
        print(f"start {my_id}")
        with open(_skeleton_path, 'r') as _f:
            _skeleton_json = json.load(_f)
        with open(_failed_test_path, mode="r") as _f:
            _failed_test = json.load(_f)
        with open(locate_file_path, 'r') as _f:
            _locate_files = json.load(_f)['response']
        with open(_method_content_path, 'r') as _f:
            _method_content = json.load(_f)
        with open(locate_line_path, 'r') as _f:
            _possible_bug_locations_list = json.load(_f)['responses']
        _locate_files = _locate_files.split("\n")

        def join_methods(methods):
            return "\n".join([
                f"#### {_method_name} ####\n{methods[_method_name]}"
                for _method_name in methods
            ])

        _failed_test = "\n".join([
            f"### {_file_name} ###\n{join_methods(_failed_test[_file_name])}"
            for _file_name in _failed_test
        ])
        _skeleton = StringIO()
        for _locate_file in _locate_files:
            # some of file names may have prefix while others not
            _file_name = '/testbed/' + _locate_file.removeprefix('/testbed/')
            if _file_name in _skeleton_json and _file_name in _method_content:
                _skeleton.write(f"#### {_file_name} ####\n")
                _method_map = _skeleton_json[_file_name]
                _method_content = _method_content[_file_name]
                for _method in _method_map:
                    if _method in _method_content:
                        _skeleton.write(_method_content[_method])
                        _skeleton.write("\n")
        _skeleton = _skeleton.getvalue()
        if _skeleton.isspace() or _skeleton == "":
            print(f'{my_id} located file does not exist in related.')
            return
        if _add_issue:
            # noinspection PyBroadException
            try:
                issue_content = "\n### issue info ###\n"
                issue_content += _instance['problem_statement']
            except:
                issue_content = ""
        else:
            issue_content = ""
        if _add_stack:
            _stack_info = "\n### Stack Trace in Failed Test Case(s) ###\n"
            _stack_info += open(_stack_path, 'r').read()
            if not _stack_info:
                print(f"no failed test in {my_id}")
                return
        else:
            _stack_info = ""
        if _add_debug:
            _debug_info = "\n### Debug Information ###\n"
            _debug_info += open(debug_info_path, 'r').read()
            if not _debug_info:
                print(f"no debug info in {my_id}")
                return
        else:
            _debug_info = ""
        _results = []
        for _possible_bug_locations in set(_possible_bug_locations_list):
            chat = Chat.Chat(MODULE_NAME, SYS_PROMPT)
            user_prompt = LocateLinePrompt.format(
                skeleton_of_files=_skeleton,
                stack_info=_stack_info,
                failed_tests=_failed_test,
                issue_content=issue_content,
                debug_info=_debug_info,
                possible_bug_locations=_possible_bug_locations,
            )
            if not _dry_run:
                try:
                    messages = chat.chat(user_prompt, 3)
                except Exception as e:
                    traceback.print_exc()
                    return
                _result = {
                    "system_prompt": SYS_PROMPT,
                    "user_prompt": user_prompt,
                    "responses": messages,
                }
                _results.append(_result)
            else:
                print(user_prompt)
        print(f"finish chat in {my_id}")
        with open(_output_path / f"{my_id}.json", "w") as _f:
            json.dump(_results, _f)
        print(f"finish {my_id}")


    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    # __do_extract(instances[0])
    # for i in instances:
    # if i['repo'] != 'django/django':
    #         continue
    #     do_extract(i)
    # if i['repo'] == 'django/django':
    #     break

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                do_extract,
                _i,
            )
            for _i in instances
        ]
    concurrent.futures.wait(futures)
