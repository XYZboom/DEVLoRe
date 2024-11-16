import concurrent.futures
import subprocess
import os

import dotenv
import tqdm
from dotenv import load_dotenv, find_dotenv

import defects4j_utils
from BugAutoFixV1.Project import Project

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


def extract_method_signatures(_path, _output, _related_methods):
    _process = subprocess.Popen(["java", "-jar", EXTRACT_JAR_PATH,
                                 "-i", _path, "-o", _output, "-f", _related_methods,
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

    if not os.path.exists(f"{D4J_JSON_PATH}/result_skeleton"):
        os.mkdir(f"{D4J_JSON_PATH}/result_skeleton")

    def do_extract(pid, bid):
        _output_path = f"{D4J_JSON_PATH}/result_skeleton/{pid}_{bid}b.json"
        _failed_test_path = f"{D4J_JSON_PATH}/result_failed_tests_method_content/{pid}_{bid}b.json"
        if os.path.exists(_output_path) and os.path.exists(_failed_test_path):
            print(f"{pid}_{bid}b exists.")
            return
        # if f"{pid}_{bid}b" in finished:
        #     print(f"{pid}_{bid}b exists.")
        #     return
        print(f"checkout: {pid}_{bid}b")
        with tempfile.TemporaryDirectory() as temp_dir:
            checkout(pid, bid, temp_dir)
            if not os.path.exists(temp_dir):
                print(f"{pid}_{bid}b checkout failed.")
                return
            print(f"{pid}_{bid}b checkout success.")
            project = Project(temp_dir)
            trigger_test_methods = project.trigger_test_methods().split(",")
            for method in trigger_test_methods:
                project.run_test(False, method)
            with open(os.path.join(temp_dir, "methodRecorder.log"), "r") as _f:
                _related_methods = ",".join(_f.read().strip().splitlines())
            if not os.path.exists(_output_path):
                extract_method_signatures(temp_dir, _output_path, _related_methods)
            if not os.path.exists(_failed_test_path):
                extract_trigger_test(temp_dir, _failed_test_path)
        with open(f"{D4J_JSON_PATH}/first_step.txt", "a") as _f:
            _f.write(f"{pid}_{bid}b\n")
        print(f"{pid}_{bid}b done.")


    # for pid, bid in tqdm.tqdm(list(defects4j_utils.d4j_pids_bids())):
    #     do_extract(pid, bid)
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=128
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
