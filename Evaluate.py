import json
import os
import re
from tqdm import tqdm
import traceback
import subprocess
import tempfile
import load_env
from BugAutoFixV1.Project import Project

import defects4j_utils

load_env.load_env()
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
D4J_JSON_PATH = os.environ.get("D4J_JSON_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")
D4J_TRIGGER_KEY = "d4j.tests.trigger"
D4J_RELEVANT_KEY = "d4j.classes.relevant"
D4J_PROPERTIES_FILE = "defects4j.build.properties"

SEARCH_KEY = "search"
REPLACE_KEY = "replace"
CLASS_KEY = "class"


def extract_replace(_raw_response):
    pattern1 = r"```java[^\n]*\n((.*\n)*?)```\s*"
    matches = re.findall(pattern1, _raw_response)
    if not matches:
        return None
    _result = []
    for match in matches:
        inner_matches = match[0].split("###")
        for inner_match in inner_matches:
            if not inner_match:
                continue
            split1 = inner_match.split("<<<<<<< SEARCH")
            if len(split1) != 2:
                for _1 in split1[1:]:
                    split2 = _1.split("=======")
                    if len(split2) != 2:
                        continue
                    split3 = split2[1].split(">>>>>>> REPLACE")
                    _result.append({
                        CLASS_KEY: split1[0].strip(),
                        SEARCH_KEY: split2[0].removeprefix("\n").removesuffix("\n"),
                        REPLACE_KEY: split3[0].removeprefix("\n").removesuffix("\n"),
                    })
                continue
            split2 = split1[1].split("=======")
            if len(split2) != 2:
                continue
            split3 = split2[1].split(">>>>>>> REPLACE")
            _result.append({
                CLASS_KEY: split1[0].strip(),
                SEARCH_KEY: split2[0].removeprefix("\n").removesuffix("\n"),
                REPLACE_KEY: split3[0].removeprefix("\n").removesuffix("\n"),
            })
    return _result


def diff(_ori, _dst, _patch_path):
    with open(_patch_path, "w") as _f:
        _process = subprocess.Popen(["git", "diff", _ori, _dst],
                                    stdout=_f, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    if _err:
        print(_err.decode())


def do_patch(pid, bid, _evaluate_path, _patch_dir):
    _version_str = f"{pid}_{bid}b"
    _patch_out_path = f"{_patch_dir}/{_version_str}.patch"
    if os.path.exists(_patch_out_path):
        print(f"patch exists: {_version_str}")
        return
    _write_dir = tempfile.TemporaryDirectory()
    _copy_dir = tempfile.TemporaryDirectory()
    with open(_evaluate_path, "r") as _f:
        _eval_result = json.load(_f)
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"checkout {_version_str}")
        defects4j_utils.checkout(pid, bid, temp_dir, _print_stderr=False)
        if not os.path.exists(os.path.join(temp_dir, D4J_PROPERTIES_FILE)):
            print(f"checkout failed: {_version_str}")
            return
        try:
            project = Project(temp_dir)
        except Exception as e:
            print(f"create project failed: {_version_str}")
            return
        project.apply_replace_list(_eval_result)
        with open(_patch_out_path, "w") as _f1:
            _process = subprocess.Popen(["git", "diff", ],
                                        stdout=_f1, stderr=subprocess.PIPE, cwd=temp_dir)
            _out, _err = _process.communicate()
            if _err:
                print(_err.decode())


if __name__ == '__main__':
    import threading
    import eventlet
    import argparse
    import concurrent.futures

    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-only", help="output git patch only", default=False)
    parser.add_argument("--patch-valid", help="patch only result that passed the test", default=True)
    parser.add_argument("--patch-dir", help="output git patch directory", default=False)
    parser.add_argument("--add-debug-info", help="add debug info", default=False)
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    parser.add_argument("--use-baseline-method", help="use baseline method", default=False)
    parser.add_argument("--final-eval", help="run all test to evaluate final result", default=False)
    parser.add_argument("--add-stack-info", help="add stack info", default=False)
    args = parser.parse_args()
    _add_debug = args.add_debug_info
    _add_issue = args.add_issue_info
    _baseline_method = args.use_baseline_method
    _final_eval = args.final_eval
    _add_stack = args.add_stack_info

    _repair_path = f"{OUTPUT_PATH}/Repair"
    _evaluate_path = f"{OUTPUT_PATH}/Evaluate"
    if _baseline_method:
        _repair_path += "Baseline"
        _evaluate_path += "Baseline"
    if _add_issue:
        _repair_path += "Issue"
        _evaluate_path += "Issue"
    if _add_stack:
        _repair_path += "Stack"
        _evaluate_path += "Stack"
    if _add_debug:
        _repair_path += "Debug"
        _evaluate_path += "Debug"

    _patch_path = args.patch_dir
    _patch_valid = False if args.patch_valid == 'False' else True
    if _patch_valid and not os.path.exists(_patch_path):
        os.makedirs(_patch_path)
    if not os.path.exists(_evaluate_path):
        os.mkdir(_evaluate_path)

    all_count = 0
    fixed_count = 0
    eventlet.monkey_patch()

    def evaluate(pid, bid):
        global all_count, fixed_count
        _version_str = f"{pid}_{bid}b"
        _my_evaluate_path = f"{_evaluate_path}/{_version_str}.json"
        if os.path.exists(_my_evaluate_path):
            if _final_eval:

                return

            if _patch_path is not None and not _patch_valid:
                print(f"{_version_str} exists")
                return

            if os.path.getsize(_my_evaluate_path) == 0:
                print(f"{_version_str} invalid")
                return
            if _patch_valid:
                do_patch(pid, bid, _my_evaluate_path, _patch_path)
                return
        elif args.patch_only:
            print(f"{_version_str} not found, patch only now.")
            return
        _my_repair_path = f"{_repair_path}/{_version_str}.json"
        if not os.path.isfile(_my_repair_path):
            return
        with open(_my_repair_path, "r") as f:
            _repairs_json = json.load(f)
        _repairs = []
        for _repair in _repairs_json:
            if "responses" in _repair:
                for _response in _repair["responses"]:
                    _repairs.append(_response)
        if not _repairs:
            print("no available repairs")
            return
        _success_repair = None
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"checkout {_version_str}")
            defects4j_utils.checkout(pid, bid, temp_dir)
            if not os.path.exists(temp_dir):
                print(f"checkout failed: {_version_str}")
                return
            try:
                project = Project(temp_dir)
            except Exception as e:
                print(f"create project failed: {_version_str}")
                return
            for _repair in tqdm(_repairs, desc=f"Applying repair", unit="step"):
                _replace_result = extract_replace(_raw_response=_repair)
                if not _replace_result:
                    # for debug propose
                    extract_replace(_raw_response=_repair)
                    continue
                project.undo_all_files()
                try:
                    project.apply_replace_list(_replace_result)
                except Exception as e:
                    traceback.print_exc()
                    # for debug propose
                    extract_replace(_raw_response=_repair)
                    continue
                print("apply_replace_list finished")
                try:
                    with eventlet.Timeout(600):
                        _run_test_result = project.run_test()
                except eventlet.Timeout:
                    print("execution time out")
                    # continue
                    break
                if _run_test_result == 'success':
                    try:
                        with eventlet.Timeout(1200):
                            _final_result = project.run_test(relevant=False)
                            if _final_result == "success":
                                _success_repair = _replace_result
                                break
                    except eventlet.Timeout:
                        print("execution time out")
                        break
        if _success_repair:
            print(f"success {_version_str}")
            with open(_my_evaluate_path, "w") as _f:
                json.dump(_success_repair, _f)
        else:
            print(f"fail {_version_str}")
            open(_my_evaluate_path, "w").close()

    # _all_pd = list(defects4j_utils.d4j_pids_bids())
    # for pid, bid in tqdm(_all_pd, desc="Evaluate"):
    #     evaluate(pid, bid)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=64
    ) as executor:
        futures = [
            executor.submit(
                evaluate,
                pid,
                bid
            )
            for pid, bid in list(defects4j_utils.apr2024_pids_bids())
        ]
        concurrent.futures.wait(futures)
