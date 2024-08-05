import json
import os
import re
from tqdm import tqdm
import traceback
import subprocess

import defects4j_utils

from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
D4J_JSON_PATH = os.environ.get("D4J_JSON_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")
D4J_TRIGGER_KEY = "d4j.tests.trigger"
D4J_RELEVANT_KEY = "d4j.classes.relevant"

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


if __name__ == '__main__':
    from BugAutoFixV1.Project import Project
    import threading
    import tempfile
    import eventlet
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-only", help="output git patch only", default=False)
    parser.add_argument("--patch-valid", help="patch only result that passed the test", default=True)
    parser.add_argument("--patch-dir", help="output git patch directory", default=False)
    args = parser.parse_args()

    _repair_path = f"{OUTPUT_PATH}/Repair"
    _evaluate_path = f"{OUTPUT_PATH}/Evaluate"
    _patch_path = args.patch_dir
    _patch_valid = args.patch_valid
    if not os.path.exists(_evaluate_path):
        os.mkdir(_evaluate_path)

    all_count = 0
    fixed_count = 0
    all_count_lock = threading.Lock()
    fixed_count_lock = threading.Lock()


    def evaluate(pid, bid):
        global all_count, fixed_count
        _version_str = f"{pid}_{bid}b"
        _my_evaluate_path = f"{_evaluate_path}/{_version_str}.json"
        if os.path.exists(_my_evaluate_path):
            if _patch_path is not None and not _patch_valid:
                print(f"{_version_str} exists")
                return

            if os.path.getsize(_my_evaluate_path) == 0:
                print(f"{_version_str} invalid")
                return

            def do_patch():
                _patch_out_path = f"{_patch_path}/{_version_str}.patch"
                if os.path.exists(_patch_out_path):
                    print(f"patch exists: {_version_str}")
                    return
                _write_dir = tempfile.TemporaryDirectory()
                _copy_dir = tempfile.TemporaryDirectory()
                with open(_my_evaluate_path, "r") as _f:
                    _eval_result = json.load(_f)
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
                    project.apply_replace_list(_eval_result)
                    with open(_patch_out_path, "w") as _f1:
                        _process = subprocess.Popen(["git", "diff", ],
                                                    stdout=_f1, stderr=subprocess.PIPE, cwd=temp_dir)
                        _out, _err = _process.communicate()
                        if _err:
                            print(_err.decode())

            if _patch_valid:
                do_patch()
                return
        elif args.patch_only:
            print(f"{_version_str} not found, patch only now.")
            return
        _my_repair_path = f"{_repair_path}/{_version_str}.json"
        if not os.path.isfile(_my_repair_path):
            return
        with all_count_lock:
            all_count += 1
        with open(_my_repair_path, "r") as f:
            _repairs_json = json.load(f)
        _repairs = []
        for _repair in _repairs_json:
            if "responses" in _repair:
                for _response in _repair["responses"]:
                    _repairs.append(_response)
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
                eventlet.monkey_patch()
                try:
                    with eventlet.Timeout(300):
                        _run_test_result = project.run_test()
                        if _run_test_result == 'success':
                            _success_repair = _replace_result
                            break
                except eventlet.Timeout:
                    print("execution time out")
        if _success_repair:
            print(f"success {_version_str}")
            with open(_my_evaluate_path, "w") as _f:
                json.dump(_success_repair, _f)
            with fixed_count_lock:
                fixed_count += 1
        else:
            print(f"fail {_version_str}")
            open(_my_evaluate_path, "w").close()


    # for pid, bid in defects4j_utils.d4j_pids_bids():
    #     evaluate(pid, bid)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=8
    ) as executor:
        futures = [
            executor.submit(
                evaluate,
                pid,
                bid
            )
            for pid, bid in defects4j_utils.d4j_pids_bids()
        ]
        concurrent.futures.wait(futures)
