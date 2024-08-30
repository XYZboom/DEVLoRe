import os
import traceback

import defects4j_utils

from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
D4J_JSON_PATH = os.environ.get("D4J_JSON_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")
D4J_TRIGGER_KEY = "d4j.tests.trigger"
D4J_RELEVANT_KEY = "d4j.classes.relevant"

LocateLinePrompt = """Review the following methods and(or) fields of classes, test case(s), 
and exception that occurs when doing the test.
Provide a set of locations that need to be edited to fix the issue. 
The locations must be specified as line number in class.
### Skeleton of Classes ###
{skeleton_of_classes}
### Failed Test Case(s) and exception ###
{failed_tests}
{debug_info}

Please provide class name and line number that need to be edited.
### Examples:
```
path.to.ClassA
line: 20
line: 45
line: 46
line: 47
```
```
path.to.ClassB
line: 20
line: 45
path.to.ClassC
line: 256
line: 451
```
Return just the location(s)
"""

SYS_PROMPT = "You are a software development engineer"

if __name__ == '__main__':
    import Chat
    import json
    import argparse
    import concurrent.futures

    parser = argparse.ArgumentParser()
    parser.add_argument("--add-debug-info", help="add debug info", default=False)
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    args = parser.parse_args()

    _add_debug = args.add_debug_info
    _add_issue = args.add_issue_info

    if _add_debug:
        if not _add_issue:
            _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method"
            _locate_line_path = f"{OUTPUT_PATH}/LocateLineDebug"
        else:
            _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method_issue"
            _locate_line_path = f"{OUTPUT_PATH}/LocateLineIssueDebug"
    elif _add_issue:
        _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method_issue"
        _locate_line_path = f"{OUTPUT_PATH}/LocateLineIssue"
    else:
        _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method"
        _locate_line_path = f"{OUTPUT_PATH}/LocateLine"

    if not os.path.exists(_locate_line_path):
        os.makedirs(_locate_line_path)


    def do_extract(pid, bid):
        if os.path.exists(f"{_locate_line_path}/{pid}_{bid}b.json"):
            print(f"{pid}_{bid}b exists.")
            return
        _buggy_method_file = f"{_buggy_method_path}/{pid}_{bid}b.json"
        _failed_test_path = f"{D4J_JSON_PATH}/result_failed_tests_method_content/{pid}_{bid}b.json"
        if not os.path.exists(_buggy_method_file) or not os.path.exists(_failed_test_path):
            print(f"buggy method or failed test of {pid}_{bid}b not exists.")
            return
        _debug_path = f"{OUTPUT_PATH}/DebugInfo/{pid}_{bid}b.txt"
        if not os.path.exists(_debug_path) and _add_debug:
            print(f"debug info not exists when --add-debug-info is True. {pid}_{bid}b")
            return
        if _add_debug and (os.path.getsize(_debug_path) == 0 or os.path.getsize(_debug_path) > 20 * 1024):
            print(f"{pid}_{bid}b debug info is empty or size too large.")
            return
        _debug_info = ""
        if _add_debug:
            with open(_debug_path, "r") as _f:
                _debug_info = "### Debug info ###\n"
                _debug_info += _f.read()
        print(f"start {pid}_{bid}b")
        chat = Chat.Chat("gpt-4o-mini", SYS_PROMPT)
        with open(_buggy_method_file, mode="r") as _f:
            _buggy_method = json.load(_f)
        _skeleton_of_classes = "\n".join([
            f"### {_class} ###\n{_buggy_method[_class]}"
            for _class in _buggy_method
        ])
        _failed_tests = defects4j_utils.trigger_test_stacktrace(pid, bid)
        if not _failed_tests:
            print(f"no failed test in {pid}_{bid}b")
            return
        user_prompt = LocateLinePrompt.format(
            skeleton_of_classes=_skeleton_of_classes,
            failed_tests=_failed_tests,
            debug_info=_debug_info,
        )
        try:
            messages = chat.chat(user_prompt, 10)
        except Exception as e:
            traceback.print_exc()
            return
        _result = {
            "system_prompt": SYS_PROMPT,
            "user_prompt": user_prompt,
            "responses": messages,
        }
        print(f"finish chat in {pid}_{bid}b")
        with open(f"{_locate_line_path}/{pid}_{bid}b.json", "w") as _f:
            json.dump(_result, _f)
        print(f"finish {pid}_{bid}b")


    # for pid, bid in defects4j_utils.d4j_pids_bids():
    #     do_extract(pid, bid)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=32
    ) as executor:
        futures = [
            executor.submit(
                do_extract,
                pid,
                bid
            )
            for pid, bid in defects4j_utils.d4j_pids_bids()
        ]
        concurrent.futures.wait(futures)
