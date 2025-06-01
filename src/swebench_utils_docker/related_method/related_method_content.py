import json
import os
import ast
import typing
from _ast import FunctionDef
from collections import defaultdict
from io import StringIO
from typing import List, TypedDict, Dict, Set

from dotenv import load_dotenv, find_dotenv

from src.common_utils import record_error_stack
from src.swebench_utils.swebench_utils import handle_swe_failed_test
from src.swebench_utils_docker.docker_utils import copy_from_container

_ = load_dotenv(find_dotenv())
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


def methods_from_ast(_source_code) -> List[Method]:
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
    result = StringIO()
    for raw_num, line in enumerate(lines[start_idx:end_idx]):
        line_num = raw_num + start_idx + 1
        result.write(str(line_num))
        result.write('|')
        result.write(line)
        result.write('\n')
    return result.getvalue()


@record_error_stack
def __do_extract(_instance: SWEbenchInstance):
    my_id = _instance['instance_id']
    related_method_path = Path(SWEBENCH_LITE_PREPARE_PATH) / f'related_methods/{my_id}.json'
    if not related_method_path.exists():
        print(f'{my_id} not exists')
        return
    result_path = Path(SWEBENCH_LITE_PREPARE_PATH) / f'related_method_content/{my_id}.json'
    if result_path.exists():
        print(f'{my_id} exists')
        return
    result_path.parent.mkdir(parents=True, exist_ok=True)
    repo_name = _instance['repo']
    client = docker.from_env(timeout=120)
    test_spec = make_test_spec(
        _instance, namespace="swebench"
    )
    logger_dir = Path(OUTPUT_PATH) / 'logs' / my_id
    logger = setup_logger(my_id, logger_dir / f'{my_id}.log')
    build_instance_image(test_spec, client, logger, True)
    try:
        container = client.containers.get(test_spec.get_instance_container_name(RUN_ID))
    except docker.errors.NotFound:
        container = build_container(test_spec, client, RUN_ID, logger, True)
    container.start()
    with open(related_method_path, 'r') as related_method_file:
        related_method = json.load(related_method_file)
    result: Dict[str, Dict[str, str]] = defaultdict(dict)
    for file_name in related_method:
        try:
            (file_content, _, _) = exec_run_with_timeout(container, f'cat {file_name}', timeout=None)
            method_names = related_method[file_name]
            methods = methods_from_ast(file_content)
            for method in methods:
                if method['name'] not in method_names:
                    continue
                result[file_name][method['name']] = extract_method_content(method, file_content)
        except:
            continue
    with open(result_path, 'w') as result_file:
        json.dump(result, result_file)


if __name__ == '__main__':
    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    # __do_extract(instances[0])
    # for i in instances:
    #     if i['repo'] != 'django/django':
    #         continue
    #     __do_extract(i)
    #     if i['repo'] == 'django/django':
    #         break
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                __do_extract,
                _i,
            )
            for _i in instances
        ]
    concurrent.futures.wait(futures)
