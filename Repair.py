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
### Possible bug locations (for your reference only) ###
{possible_bug_locations}

Please first localize the bug based on the issue statement, and then generate *SEARCH/REPLACE* edits to fix the issue.

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

Please note that the *SEARCH/REPLACE* edit REQUIRES PROPER INDENTATION. 
Wrap the *SEARCH/REPLACE* edit in blocks ```java...```.
"""

SYS_PROMPT = "You are a software development engineer"

if __name__ == '__main__':
    import Chat
    import json
    import argparse
    import concurrent.futures

    _finished_path = f"{D4J_JSON_PATH}/repair.txt"

    if not os.path.exists(_finished_path):
        open(_finished_path, "w").close()
    with open(_finished_path, "r") as f:
        finished = f.read().splitlines()

    _locate_line_prefix = f"{OUTPUT_PATH}/LocateLine"
    _repair_path = f"{OUTPUT_PATH}/Repair"

    if not os.path.exists(_repair_path):
        os.makedirs(_repair_path)


    def do_extract(pid, bid):
        if os.path.exists(f"{_repair_path}/{pid}_{bid}b.json"):
            print(f"{pid}_{bid}b exists.")
            return
        _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method/{pid}_{bid}b.json"
        _failed_test_path = f"{D4J_JSON_PATH}/result_failed_tests_method_content/{pid}_{bid}b.json"
        _locate_line_path = f"{_locate_line_prefix}/{pid}_{bid}b.json"
        if not os.path.exists(_buggy_method_path) or not os.path.exists(_failed_test_path)\
                or not os.path.exists(_locate_line_path):
            return
        print(f"start {pid}_{bid}b")
        with open(_locate_line_path, "r") as _f:
            _locate_line_json = json.load(_f)
        with open(_buggy_method_path, mode="r") as _f:
            _buggy_method = json.load(_f)
        _skeleton_of_classes = "\n".join([
            f"### {_class} ###\n{_buggy_method[_class]}"
            for _class in _buggy_method
        ])
        _failed_tests = defects4j_utils.trigger_test_stacktrace(pid, bid)
        if not _failed_tests:
            print(f"no failed test in {pid}_{bid}b")
            return
        _results = []
        _locate_lines = set(_locate_line_json['responses'])
        for _locate_line in _locate_lines:
            user_prompt = LocateLinePrompt.format(
                skeleton_of_classes=_skeleton_of_classes,
                failed_tests=_failed_tests,
                possible_bug_locations=_locate_line
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
        with open(_finished_path, "a") as _f:
            _f.write(f"{pid}_{bid}b\n")
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