import concurrent.futures
import json
import subprocess
import os
import re

import dotenv
from dotenv import load_dotenv, find_dotenv

import defects4j_utils

_ = load_dotenv(find_dotenv())
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")
D4J_JSON_PATH = os.environ.get("D4J_JSON_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")


def extract_buggy_method(_path, _members, _output):
    _process = subprocess.Popen(["java", "-jar", EXTRACT_JAR_PATH,
                                 "-i", _path, "-o", _output, "-f", _members, ],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    if _err:
        print(_err.decode())


def handle_raw_response(_raw_response):
    pattern = r"^```[^\n]*\n(.*\n)*```\s*$"
    #               ^^^^^ match all char expect \n
    #                                 ^^^  match spaces at the end
    match = re.search(pattern, _raw_response, re.DOTALL)
    if not match:
        return None
    return ",".join(match.group().split("\n")[1:-1])


if __name__ == '__main__':
    import tempfile

    _finished_record = f"{D4J_JSON_PATH}/second_step.txt"
    if not os.path.exists(_finished_record):
        open(_finished_record, "w").close()
    with open(_finished_record, "r") as f:
        finished = f.read().splitlines()

    _buggy_method_path = f"{D4J_JSON_PATH}/buggy_method"
    if not os.path.exists(_buggy_method_path):
        os.makedirs(_buggy_method_path)


    def do_extract(pid, bid):
        _version_str = f"{pid}_{bid}b"
        _buggy_output = f"{_buggy_method_path}/{pid}_{bid}b.json"
        # if _version_str in finished:
        #     print(f"{_version_str} exists")
        if os.path.exists(_buggy_output):
            with open(_buggy_output, "r") as _f:
                _buggy = json.load(_f)
            if _buggy is not None and len(_buggy.keys()) != 0:
                print(f"{_version_str} exists")
                return
            else:
                os.remove(_buggy_output)
        _locate_output_path = f"{OUTPUT_PATH}/LocateMethod/{pid}_{bid}b.json"
        if not os.path.exists(_locate_output_path):
            # print(f"{pid}_{bid}b method location not found.")
            return
        with open(_locate_output_path, "r") as _f:
            _locate_json = json.load(_f)
        _raw_response = _locate_json['response']
        _handled = handle_raw_response(_raw_response)
        if not _handled:
            print(_version_str, _raw_response)
            return
        print(f"checkout: {pid}_{bid}b")
        with tempfile.TemporaryDirectory() as temp_dir:
            defects4j_utils.checkout(pid, bid, temp_dir)
            if not os.path.exists(temp_dir):
                print(f"{pid}_{bid}b checkout failed.")
                return
            print(f"{pid}_{bid}b checkout success.")
            extract_buggy_method(temp_dir, _handled, _buggy_output)
        with open(f"{D4J_JSON_PATH}/second_step.txt", "a") as _f:
            _f.write(f"{pid}_{bid}b\n")
        print(f"{pid}_{bid}b done.")

    for pid, bid in defects4j_utils.d4j_pids_bids():
        do_extract(pid, bid)
    # with concurrent.futures.ThreadPoolExecutor(
    #         max_workers=32
    # ) as executor:
    #     futures = [
    #         executor.submit(
    #             do_extract,
    #             pid,
    #             bid
    #         )
    #         for pid, bid in defects4j_utils.d4j_pids_bids()
    #     ]
    #     concurrent.futures.wait(futures)
