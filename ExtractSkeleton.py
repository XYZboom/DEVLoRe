import concurrent.futures
import subprocess
import os

import dotenv
from dotenv import load_dotenv, find_dotenv

import defects4j_utils

_ = load_dotenv(find_dotenv())
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
D4J_JSON_PATH = os.environ.get("D4J_JSON_PATH")
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")
D4J_TRIGGER_KEY = "d4j.tests.trigger"
D4J_RELEVANT_KEY = "d4j.classes.relevant"


def all_project_ids():
    _process = subprocess.Popen([D4J_EXEC, "pids"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    return _out.decode().splitlines()


def bug_ids(_pid):
    _process = subprocess.Popen([D4J_EXEC, "bids", "-p", _pid],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    return _out.decode().splitlines()


def checkout(_pid, _bid, _path):
    _process = subprocess.Popen([D4J_EXEC, "checkout", "-p", _pid, "-v", f"{_bid}b", "-w", _path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    print(_out.decode())
    if _err:
        print(_err.decode())


def extract_method_signatures(_path, _output):
    _d4j_file_name = os.path.join(_path, "defects4j.build.properties")
    _d4j_configs = dotenv.dotenv_values(_d4j_file_name)
    _relevant_classes = _d4j_configs.get(D4J_RELEVANT_KEY)
    if not _relevant_classes:
        return
    _process = subprocess.Popen(["java", "-jar", EXTRACT_JAR_PATH,
                                 "-i", _path, "-o", _output, "-fc", _relevant_classes,
                                 "-s", "--no-line-number"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    if _err:
        print(_err.decode())


def extract_trigger_test(_path, _output):
    _d4j_file_name = os.path.join(_path, "defects4j.build.properties")
    _d4j_configs = dotenv.dotenv_values(_d4j_file_name)
    _trigger = _d4j_configs.get(D4J_TRIGGER_KEY)
    if not _trigger:
        return
    _process = subprocess.Popen(["java", "-jar", EXTRACT_JAR_PATH,
                                 "-i", _path, "-o", _output, "-f", _trigger,
                                 "--no-line-number"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    if _err:
        print(_err.decode())


def delete_temp(_path):
    _process = subprocess.Popen(["rm", "-rf", _path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    print(_out.decode())
    if _err:
        print(_err.decode())


if __name__ == '__main__':
    import tempfile
    if not os.path.exists(f"{D4J_JSON_PATH}/first_step.txt"):
        open(f"{D4J_JSON_PATH}/first_step.txt", "w").close()
    with open(f"{D4J_JSON_PATH}/first_step.txt", "r") as f:
        finished = f.read().splitlines()

    def do_extract(pid, bid):
        _output_path = f"{D4J_JSON_PATH}/result_skeleton/{pid}_{bid}b.json"
        _failed_test_path = f"{D4J_JSON_PATH}/result_failed_tests_method_content/{pid}_{bid}b.json"
        if f"{pid}_{bid}b" in finished:
            print(f"{pid}_{bid}b exists.")
            return
        print(f"checkout: {pid}_{bid}b")
        with tempfile.TemporaryDirectory() as temp_dir:
            checkout(pid, bid, temp_dir)
            if not os.path.exists(temp_dir):
                print(f"{pid}_{bid}b checkout failed.")
                return
            print(f"{pid}_{bid}b checkout success.")
            extract_method_signatures(temp_dir, _output_path)
            extract_trigger_test(temp_dir, _failed_test_path)
        with open(f"{D4J_JSON_PATH}/first_step.txt", "a") as f:
            f.write(f"{pid}_{bid}b\n")
        print(f"{pid}_{bid}b done.")


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
