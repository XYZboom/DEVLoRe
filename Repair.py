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

RepairPrompt = """Review the following methods and(or) fields of classes, test case(s), 
and exception that occurs when doing the test.
Try to fix the bug.
### Skeleton of Classes ###
{skeleton_of_classes}{failed_tests}
### Possible bug locations (for your reference only) ###
{possible_bug_locations}{debug_info}{issue_info}

Please generate *SEARCH/REPLACE* edits to fix the bug based on the info given above.

Every *SEARCH/REPLACE* edit must use this format:
1. The file path
2. The start of search block: <<<<<<< SEARCH
3. A contiguous chunk of lines to search for in the existing source code
4. The dividing line: =======
5. The lines to replace into the source code
6. The end of the replace block: >>>>>>> REPLACE

Here is an example:

```java
### com.fastxml.out.MyClass
<<<<<<< SEARCH
if (_config.method1()) {{
    _outputPtr = ptr;
    break;
}}
=======
if (_config.method1()) {{
    _outputPtr = ptr;
    addMethodNeed(ch);
    break;
}}
>>>>>>> REPLACE
```

Wrap the *SEARCH/REPLACE* edit in blocks ```java...```.
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
    parser.add_argument("--use-baseline-method", help="use baseline method", default=False)
    parser.add_argument("--add-stack-info", help="add stack info", default=False)
    args = parser.parse_args()

    _add_debug = args.add_debug_info
    _add_issue = args.add_issue_info
    _add_stack = args.add_stack_info
    _baseline_method = args.use_baseline_method

    _locate_line_prefix = f"{OUTPUT_PATH}/LocateLine"
    _repair_path = f"{OUTPUT_PATH}/Repair"
    if _baseline_method:
        _locate_line_prefix += "Baseline"
        _repair_path += "Baseline"
    if _add_issue:
        _locate_line_prefix += "Issue"
        _repair_path += "Issue"
    if _add_stack:
        _locate_line_prefix += "Stack"
        _repair_path += "Stack"
    if _add_debug:
        _locate_line_prefix += "Debug"
        _repair_path += "Debug"

    if _baseline_method:
        _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method_baseline"
    else:
        _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method"
        if _add_issue:
            _buggy_method_path += "_issue"
        if _add_stack:
            _buggy_method_path += "_stack"

    if not os.path.exists(_repair_path):
        os.makedirs(_repair_path)


    def do_extract(pid, bid):
        if os.path.exists(f"{_repair_path}/{pid}_{bid}b.json"):
            print(f"{pid}_{bid}b exists.")
            return
        _buggy_method_file = f"{_buggy_method_path}/{pid}_{bid}b.json"
        _failed_test_path = f"{D4J_JSON_PATH}/result_failed_tests_method_content/{pid}_{bid}b.json"
        _locate_line_path = f"{_locate_line_prefix}/{pid}_{bid}b.json"
        _issue_info_path = f"{OUTPUT_PATH}/issue_content/{pid}_{bid}.txt"
        if not os.path.exists(_buggy_method_file) or not os.path.exists(_failed_test_path)\
                or not os.path.exists(_locate_line_path) or (not os.path.exists(_issue_info_path) and _add_issue):
            return
        print(f"start {pid}_{bid}b")
        with open(_locate_line_path, "r") as _f:
            _locate_line_json = json.load(_f)
        with open(_buggy_method_file, mode="r") as _f:
            _buggy_method = json.load(_f)
        _skeleton_of_classes = "\n".join([
            f"### {_class} ###\n{_buggy_method[_class]}"
            for _class in _buggy_method
        ])
        if _add_stack:
            _failed_tests = "\n### Failed Test Case(s) and exception ###\n"
            _failed_tests += defects4j_utils.trigger_test_stacktrace(pid, bid)
            if not _failed_tests:
                print(f"no failed test in {pid}_{bid}b")
                return
        else:
            _failed_tests = ""
        if _baseline_method:
            _debug_file = f"{OUTPUT_PATH}/DebugInfoBaseline/{pid}_{bid}b.txt"
        elif _add_issue:
            if not _add_stack:
                _debug_file = f"{OUTPUT_PATH}/DebugInfoIssue/{pid}_{bid}b.txt"
            else:
                _debug_file = f"{OUTPUT_PATH}/DebugInfoIssueStack/{pid}_{bid}b.txt"
        else:
            _debug_file = f"{OUTPUT_PATH}/DebugInfo/{pid}_{bid}b.txt"
        if not os.path.exists(_debug_file) and _add_debug:
            print(f"debug info not exists when --add-debug-info is True. {pid}_{bid}b")
            return
        if _add_debug and (os.path.getsize(_debug_file) == 0 or os.path.getsize(_debug_file) > 20 * 1024):
            print(f"{pid}_{bid}b debug info is empty or size too large.")
            return
        if _add_issue:
            # noinspection PyBroadException
            try:
                with open(_issue_info_path, "r") as _f:
                    issue_content = "\n### issue info ###\n"
                    issue_content += _f.read()
            except:
                issue_content = ""
        else:
            issue_content = ""
        _debug_info = ""
        if _add_debug:
            with open(_debug_file, "r") as _f:
                _debug_info = "\n### Debug info ###\n"
                _debug_info += _f.read()
        _results = []
        _locate_lines = set(_locate_line_json['responses'])
        for _locate_line in _locate_lines:
            user_prompt = RepairPrompt.format(
                skeleton_of_classes=_skeleton_of_classes,
                failed_tests=_failed_tests,
                possible_bug_locations=_locate_line,
                debug_info=_debug_info,
                issue_info=issue_content
            )
            chat = Chat.Chat("gpt-4o-mini", SYS_PROMPT)
            try:
                message = chat.chat(user_prompt, 3)
            except Exception as e:
                traceback.print_exc()
                return
            _result = {
                "system_prompt": SYS_PROMPT,
                "user_prompt": user_prompt,
                "responses": message,
            }
            _results.append(_result)
        if not _results:
            return
        print(f"finish chat in {pid}_{bid}b")
        with open(f"{_repair_path}/{pid}_{bid}b.json", "w") as _f:
            json.dump(_results, _f)
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
