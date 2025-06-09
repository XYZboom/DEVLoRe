import argparse
import os
import base64
import random
import re
import json
import argparse
import concurrent.futures
import tempfile
import traceback
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import TypedDict, List, Dict
import zipfile

from dotenv import load_dotenv, find_dotenv
from tqdm import tqdm

from src import Chat
from src.common_utils import record_error_stack
from src.swebench_utils.swebench_utils import raw_data, swe_pids_bids
from swebench import MAP_REPO_TO_PARSER
from swebench.harness.constants import SWEbenchInstance, APPLY_PATCH_FAIL, RESET_FAILED, TESTS_ERROR, TESTS_TIMEOUT, \
    START_TEST_OUTPUT, END_TEST_OUTPUT, TestStatus
from swebench.harness.utils import load_swebench_dataset
import docker
import docker.errors

from src.swebench_utils_common import RUN_ID
from swebench.harness.constants import SWEbenchInstance
from swebench.harness.docker_build import build_instance_image, build_container, setup_logger, build_env_images
from swebench.harness.docker_utils import *
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.utils import load_swebench_dataset

_ = load_dotenv(find_dotenv())
SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
MODULE_NAME = os.environ.get("MODULE_NAME", "gpt-4o-mini")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))

SEARCH_KEY = "search"
REPLACE_KEY = "replace"
FILE_KEY = "file"


class MyPatch(TypedDict):
    search: str
    replace: str
    file: str


def extract_replace(_raw_response) -> List[MyPatch] | None:
    pattern1 = r"```py[^\n]*\n((.*\n)*?)```\s*"
    matches = re.findall(pattern1, _raw_response)
    if not matches:
        return None
    _result: List[MyPatch] = []
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
                        FILE_KEY: split1[0].strip(),
                        SEARCH_KEY: split2[0].removeprefix("\n").removesuffix("\n"),
                        REPLACE_KEY: split3[0].removeprefix("\n").removesuffix("\n"),
                    })
                continue
            split2 = split1[1].split("=======")
            if len(split2) != 2:
                continue
            split3 = split2[1].split(">>>>>>> REPLACE")
            _result.append({
                FILE_KEY: split1[0].strip(),
                SEARCH_KEY: split2[0].removeprefix("\n").removesuffix("\n"),
                REPLACE_KEY: split3[0].removeprefix("\n").removesuffix("\n"),
            })
    return _result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    parser.add_argument("--add-stack-info", help="add stack info", default=False)
    parser.add_argument("--add-debug-info", help="add debug info", default=False)
    args = parser.parse_args()
    _add_issue = args.add_issue_info
    _add_stack = args.add_stack_info
    _add_debug = args.add_debug_info

    _suffix = ""
    if _add_issue:
        _suffix += "Issue"
    if _add_stack:
        _suffix += "Stack"
    if _add_debug:
        _suffix += "Debug"
    _repair_path = Path(OUTPUT_PATH) / f"Repair{_suffix}"
    _output_path = Path(OUTPUT_PATH) / f"Evaluate{_suffix}"
    _tmp_dir = Path(tempfile.gettempdir())

    if not _output_path.exists():
        _output_path.mkdir()

    @record_error_stack
    def do_extract(_instance: SWEbenchInstance):
        my_id = _instance['instance_id']
        if (_output_path / f"{my_id}.zip").exists():
            print(f"{my_id} exists.")
            return
        _repair_file = _repair_path / f"{my_id}.json"
        if not _repair_file.exists():
            print(f"{my_id} does not exist.")
            return
        with open(_repair_file, "r") as f:
            _raw_repair = json.load(f)
        _raw_patches = []
        for _repair in _raw_repair:
            if "responses" in _repair:
                _raw_patches.extend(_repair['responses'])
        repo_name = _instance['repo']
        log_parser = MAP_REPO_TO_PARSER[repo_name]
        client = docker.from_env(timeout=120)
        test_spec = make_test_spec(
            _instance, namespace="swebench"
        )
        logger_dir = Path(OUTPUT_PATH) / 'logs' / my_id
        logger = setup_logger(my_id, logger_dir / 'failed_test_stacktrace.log')
        build_instance_image(test_spec, client, logger, True)
        print(f'evaluating {my_id}')
        try:
            container = client.containers.get(test_spec.get_instance_container_name(RUN_ID))
        except docker.errors.NotFound:
            container = build_container(test_spec, client, RUN_ID, logger, True)
        container.start()
        _success_patches = []
        for _repair in tqdm(_raw_patches, desc=f"Applying repair", unit="step"):
            _replace_result = extract_replace(_raw_response=_repair)
            if not _replace_result:
                # for debug propose
                extract_replace(_raw_response=_repair)
                continue
            exec_run_with_timeout(container, f'git checkout -f {_instance["base_commit"]}')
            _any_patched = False
            _changed_files = []
            for _patch in _replace_result:
                (_ls_result, _, _) = exec_run_with_timeout(container, f'ls {_patch[FILE_KEY]}')
                if _ls_result.startswith('ls: cannot access'):
                    continue
                (_cat_result, _, _) = exec_run_with_timeout(container, f'cat {_patch[FILE_KEY]}')
                if not _cat_result.__contains__(_patch[SEARCH_KEY]):
                    continue
                _new_content = _cat_result.replace(_patch[SEARCH_KEY], _patch[REPLACE_KEY])
                with open(_tmp_dir / my_id, 'w') as tf:
                    tf.write(_new_content)
                try:
                    copy_to_container(container, _tmp_dir / my_id, Path(_patch[FILE_KEY]))
                except:
                    continue
                (_cat_patched, _, _) = exec_run_with_timeout(container, f'cat {_patch[FILE_KEY]}')
                if _cat_patched != _new_content:
                    print("patch failed")
                    continue
                (_diff, _, _) = exec_run_with_timeout(container, f'git diff {_patch[FILE_KEY]}')
                if not _diff:
                    continue
                _changed_files.append(_patch[FILE_KEY])
            eval_path = PurePosixPath('/eval.sh')
            eval_out_docker_path = Path(logger_dir) / 'eval.sh'
            eval_out_docker_path.write_text('\n'.join(test_spec.eval_script_list))
            copy_to_container(container, eval_out_docker_path, eval_path)
            (eval_result, time_out, _) = exec_run_with_timeout(container, '/bin/bash /eval.sh')
            bad_codes = list(
                filter(
                    lambda x: x in eval_result,
                    [
                        APPLY_PATCH_FAIL,
                        RESET_FAILED,
                        TESTS_ERROR,
                        TESTS_TIMEOUT,
                    ],
                )
            )
            if bad_codes or time_out:
                continue
            elif not (START_TEST_OUTPUT in eval_result and END_TEST_OUTPUT in eval_result):
                # Test patch did not apply (should not happen at all)
                continue

            # Get status map of evaluation results
            eval_result = eval_result.split(START_TEST_OUTPUT)[1].split(END_TEST_OUTPUT)[0]
            parsed_eval_result: Dict[str, str] = log_parser(eval_result, test_spec)
            if not parsed_eval_result or any((v in [TestStatus.FAILED.value, TestStatus.ERROR.value]
                                              for v in parsed_eval_result.values())):
                continue
            (_diff_all, _, _) = exec_run_with_timeout(container, f'git diff {" ".join(_changed_files)}')
            _success_patches.append(_diff_all)
        _output_file = _output_path / f"{my_id}.zip"
        with zipfile.ZipFile(_output_file, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for _i, _patch in enumerate(set(_success_patches)):
                zf.writestr(f'{_i}.patch', _patch)
        if _success_patches:
            print(f'{my_id} success, patch number: {len(_success_patches)}')

        print(f'finish {my_id}')

    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    # __do_extract(instances[0])
    # for i in instances:
        # if i['repo'] != 'django/django':
        #         continue
        # do_extract(i)
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
