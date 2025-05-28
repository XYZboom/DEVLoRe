import json
import os

from dotenv import load_dotenv, find_dotenv

_ = load_dotenv(find_dotenv())

from src.common_utils import record_error_stack
from src.swebench_utils.swebench_utils import handle_swe_failed_test
from src.swebench_utils_docker.docker_utils import copy_from_container
import ast
from _ast import FunctionDef
from typing import List, Dict, Literal, TypedDict
import unidiff
from collections import defaultdict

OUTPUT_PATH = os.environ.get('OUTPUT_PATH')
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', default=16))
SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")

import sys
from pathlib import Path, PurePosixPath
import concurrent.futures

import docker
import docker.errors

from src.swebench_utils_common import RUN_ID
from swebench.harness.constants import SWEbenchInstance
from swebench.harness.docker_build import build_instance_image, build_container, setup_logger, build_env_images
from swebench.harness.docker_utils import *
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.utils import load_swebench_dataset


class Method(TypedDict):
    start: int
    end: int
    name: str
    node: FunctionDef


def affect_methods_from_ast(_source_code) -> List[Method]:
    _methods: List[Method] = []
    tree = ast.parse(_source_code)

    class MethodVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: FunctionDef):
            start_line = node.lineno
            end_line = node.end_lineno
            _methods.append({
                "name": node.name,
                "start": start_line,
                "end": end_line,
                "node": node
            })
            self.generic_visit(node)

    visitor = MethodVisitor()
    visitor.visit(tree)
    return _methods

def extract_method_content(_method: Method, _source_code):
    lines = _source_code.split('\n')
    start_idx = _method['start'] - 1
    end_idx = _method['end']
    return '\n'.join(lines[start_idx:end_idx])


@record_error_stack
def __do_extract(_instance: SWEbenchInstance):
    my_id = _instance['instance_id']
    _result_path = Path(SWEBENCH_LITE_PREPARE_PATH) / f'failed_test_content/{my_id}.json'
    if _result_path.exists():
        print(f'{my_id} exists')
        return
    repo_name = _instance['repo']
    client = docker.from_env(timeout=120)
    test_spec = make_test_spec(
        _instance, namespace="swebench"
    )
    logger_dir = Path(OUTPUT_PATH) / 'logs' / my_id
    logger = setup_logger(my_id, logger_dir / 'failed_test_stacktrace.log')
    build_instance_image(test_spec, client, logger, True)
    print(f'extracting failed_test content: {my_id}')
    try:
        container = client.containers.get(test_spec.get_instance_container_name(RUN_ID))
    except docker.errors.NotFound:
        container = build_container(test_spec, client, RUN_ID, logger, True)
    container.start()


    def get_affected_methods(_patch_content: str, _source_root) -> Dict[str, List[Method]]:
        _affected_methods = defaultdict(list)
        patch = unidiff.PatchSet(_patch_content)

        for patched_file in patch:
            _file_path = Path(_source_root) / patched_file.target_file[2:]
            (_source_code, _, _) = exec_run_with_timeout(container, f'cat {str(_file_path)}')
            _methods = affect_methods_from_ast(_source_code)

            for hunk in patched_file:
                start_line = hunk.target_start
                end_line = start_line + hunk.target_length - 1

                for _method in _methods:
                    if _method['start'] <= start_line <= _method['end'] or \
                            _method['start'] <= end_line <= _method['end']:
                        _affected_methods[str(_file_path)].append(_method)

        return _affected_methods

    eval_cmd_list = test_spec.eval_script_list.copy()
    # apply git patch
    git_patch_path = PurePosixPath('/git_patch.sh')
    git_patch_out_docker_path = Path(logger_dir) / 'git_patch.sh'
    git_patch_out_docker_path.write_text('\n'.join([eval_cmd_list[-6], eval_cmd_list[-5]]))
    copy_to_container(container, git_patch_out_docker_path, git_patch_path)
    exec_run_with_timeout(container, '/bin/bash /git_patch.sh', None)
    _affected_methods = get_affected_methods(_instance['test_patch'], '/testbed')
    _result_dict = defaultdict(dict)

    for _file_path, _methods in _affected_methods.items():
        (_source_code, _, _) = exec_run_with_timeout(container, f'cat {str(_file_path)}')

        for _method in _methods:
            _content = extract_method_content(_method, _source_code)
            _result_dict[_file_path.replace('/testbed', '')][_method['name']] = _content

    if not _result_path.parent.exists():
        _result_path.parent.mkdir()
    if len(_result_dict) == 0:
        return
    with open(_result_path, 'w') as _f:
        json.dump(_result_dict, _f)

    # unapply git patch
    exec_run_with_timeout(container, eval_cmd_list[-1], None)
    print(f'end extracting failed_test content: {my_id}')


if __name__ == '__main__':
    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    # __do_extract(instances[0])
    for i in instances:
        # if i['repo'] != 'django/django':
        #     continue
        __do_extract(i)
        # if i['repo'] == 'django/django':
        #     break
    # with concurrent.futures.ThreadPoolExecutor(
    #         max_workers=MAX_WORKERS
    # ) as executor:
    #     futures = [
    #         executor.submit(
    #             __do_extract,
    #             _i,
    #         )
    #         for _i in instances
    #     ]
    # concurrent.futures.wait(futures)
