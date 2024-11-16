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

LocateMethodPrompt = """Review the following skeleton of classes, test case(s), 
and exception that occurs when doing the test.
Provide a set of locations that need to be edited to fix the issue. 
The locations must be specified as method names or field names.
### Skeleton of Classes ###
{skeleton_of_classes}{failed_tests}{issue_content}

Please provide method names or field names that need to be edited.
### Examples:
```
path.to.ClassA::methodA
path.to.ClassA::methodB
path.to.ClassB::methodA
```
```
path.to.ClassC::fieldA
path.to.ClassD::methodB
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
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    parser.add_argument("--add-stack-info", help="add stack info", default=False)
    args = parser.parse_args()
    _add_issue = args.add_issue_info
    _add_stack = args.add_stack_info

    if not os.path.exists(f"{D4J_JSON_PATH}/first_step_llm.txt"):
        open(f"{D4J_JSON_PATH}/first_step_llm.txt", "w").close()
    with open(f"{D4J_JSON_PATH}/first_step_llm.txt", "r") as f:
        finished = f.read().splitlines()

    if _add_stack:
        if _add_issue:
            _output_path = f"{OUTPUT_PATH}/LocateMethodIssueStack"
        else:
            _output_path = f"{OUTPUT_PATH}/LocateMethodStack"
    elif _add_issue:
        _output_path = f"{OUTPUT_PATH}/LocateMethodIssue"
    else:
        _output_path = f"{OUTPUT_PATH}/LocateMethod"

    if not os.path.exists(_output_path):
        os.makedirs(_output_path)

    def do_extract(pid, bid):
        if os.path.exists(f"{_output_path}/{pid}_{bid}b.json"):
            print(f"{pid}_{bid}b exists.")
            return
        _skeleton_path = f"{D4J_JSON_PATH}/result_skeleton/{pid}_{bid}b.json"
        _issue_info_path = f"{OUTPUT_PATH}/issue_content/{pid}_{bid}.txt"
        if not os.path.exists(_skeleton_path) \
                or (not os.path.exists(_issue_info_path) and _add_issue):
            print(f"not enough info for {pid}_{bid}b")
            return
        print(f"start {pid}_{bid}b")
        chat = Chat.Chat("gpt-4o-mini", SYS_PROMPT)
        with open(_skeleton_path, mode="r") as _f:
            _skeleton = json.load(_f)
        _skeleton_of_classes = "\n".join([
            f"### {_class} ###\n{_skeleton[_class]}"
            for _class in _skeleton
        ])
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
        if _add_stack:
            _failed_tests = "\n### Failed Test Case(s) and exception ###\n"
            _failed_tests += defects4j_utils.trigger_test_stacktrace(pid, bid)
            if not _failed_tests:
                print(f"no failed test in {pid}_{bid}b")
                return
        else:
            _failed_tests = ""
        user_prompt = LocateMethodPrompt.format(
            skeleton_of_classes=_skeleton_of_classes,
            failed_tests=_failed_tests,
            issue_content=issue_content
        )
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
        with open(f"{D4J_JSON_PATH}/first_step_llm.txt", "a") as _f:
            _f.write(f"{pid}_{bid}b\n")
        print(f"finish {pid}_{bid}b")


    # for pid, bid in defects4j_utils.d4j_pids_bids():
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
            for pid, bid in defects4j_utils.apr2024_pids_bids()
        ]
        concurrent.futures.wait(futures)
