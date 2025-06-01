import os
from typing import List

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

__lock = threading.Lock()


def __handle_failed_tests(failed_tests: List[str]) -> str:
    __result_set = set()

    for failed_test in failed_tests:
        if '[' in failed_test:
            __result_set.add(failed_test[:failed_test.index('[')])
        else:
            __result_set.add(failed_test)

    return ' '.join(__result_set)


@record_error_stack
def __do_extract(_instance: SWEbenchInstance):
    my_id = _instance['instance_id']
    _result_path = Path(SWEBENCH_LITE_PREPARE_PATH) / f'related_methods/{my_id}.json'
    if _result_path.exists():
        print(f'{my_id} exists')
        return
    repo_name = _instance['repo']
    client = docker.from_env(timeout=120)
    test_spec = make_test_spec(
        _instance, namespace="swebench"
    )
    logger_dir = Path(OUTPUT_PATH) / 'logs' / my_id
    logger = setup_logger(my_id, logger_dir / f'{my_id}.log')
    build_instance_image(test_spec, client, logger, True)
    print(f'extracting related methods: {my_id}')
    try:
        container = client.containers.get(test_spec.get_instance_container_name(RUN_ID))
    except docker.errors.NotFound:
        container = build_container(test_spec, client, RUN_ID, logger, True)
    container.start()
    detailed_failed_test = handle_swe_failed_test(_instance['FAIL_TO_PASS'], repo_name == 'django/django')
    failed_test = __handle_failed_tests(detailed_failed_test)
    # print(handle_swe_failed_test(_instance['FAIL_TO_PASS']))
    # print(failed_test)
    # return
    if repo_name == 'sympy/sympy':
        eval_py_path = PurePosixPath('/extract_related_method.py')
        try:
            # copy_to_container may delete a non-exists file
            copy_to_container(container, Path(__file__).parent / 'do_extract_related_method_sympy.py', eval_py_path)
        except:
            pass
        eval_cmd_list = test_spec.eval_script_list.copy()
        for i, eval_cmd in enumerate(eval_cmd_list):
            if eval_cmd.startswith('git checkout'):
                eval_cmd_list[i] = ' '.join(eval_cmd.split(' ')[:3]) + ' -f'
        want_cmd_list = []
        _exec_met = False
        for cmd in eval_cmd_list[-3].split(' '):
            if _exec_met:
                if not cmd.startswith('-'):
                    want_cmd_list.append(cmd)
            elif cmd.startswith('PYTHON'):  # env setting
                want_cmd_list.append(cmd)
            elif cmd == 'bin/test':
                want_cmd_list.extend(['python', str(eval_py_path), '/testbed/bin/test', '/testbed/bin',
                                      f'/related_methods/{my_id}.json',
                                      '-f', '/testbed', '-args'])
                _exec_met = True
        eval_cmd_list[-3] = ' '.join(want_cmd_list)
        eval_path = PurePosixPath('/eval.sh')
        eval_out_docker_path = Path(logger_dir) / 'eval.sh'
        eval_out_docker_path.write_text('\n'.join(eval_cmd_list))
        copy_to_container(container, eval_out_docker_path, eval_path)
        (eval_result, _, _) = exec_run_with_timeout(container, '/bin/bash /eval.sh', timeout=None)
        print(eval_result)
    elif repo_name != 'django/django':
        (exec_result, _, _) = exec_run_with_timeout(
            container, "bash -c 'source /opt/miniconda3/bin/activate && conda activate testbed && whereis pytest'")
        pytest_path = exec_result.removeprefix('pytest: ').removesuffix('\n')
        if pytest_path == 'pytest:':
            return
        eval_py_path = PurePosixPath('/extract_related_method.py')
        try:
            # copy_to_container may delete a non-exists file
            copy_to_container(container, Path(__file__).parent / 'do_extract_related_method_in_pytest.py', eval_py_path)
        except:
            pass
        eval_cmd_list = test_spec.eval_script_list.copy()
        for i, eval_cmd in enumerate(eval_cmd_list):
            if eval_cmd.startswith('git checkout'):
                eval_cmd_list[i] = ' '.join(eval_cmd.split(' ')[:3]) + ' -f'
        eval_cmd_list[-3] = (f'python {eval_py_path} {pytest_path} /testbed /related_methods/{my_id}.json '
                             f'-f /testbed '
                             f'-args {failed_test}')
        eval_path = PurePosixPath('/eval.sh')
        eval_out_docker_path = Path(logger_dir) / 'eval.sh'
        eval_out_docker_path.write_text('\n'.join(eval_cmd_list))
        copy_to_container(container, eval_out_docker_path, eval_path)
        (eval_result, _, _) = exec_run_with_timeout(container, '/bin/bash /eval.sh', timeout=None)
        print(eval_result)
    else:
        eval_py_path = PurePosixPath('/extract_related_method.py')
        try:
            # copy_to_container may delete a non-exists file
            copy_to_container(container, Path(__file__).parent / 'do_extract_related_method_django.py', eval_py_path)
        except:
            pass
        eval_cmd_list = test_spec.eval_script_list.copy()
        for i, eval_cmd in enumerate(eval_cmd_list):
            if eval_cmd.startswith('git checkout'):
                eval_cmd_list[i] = ' '.join(eval_cmd.split(' ')[:3]) + ' -f'
        eval_cmd_list[-3] = (f'python {eval_py_path} /testbed/tests/runtests.py /related_methods/{my_id}.json '
                             f'-f /testbed '
                             f'-args {failed_test}')
        eval_path = PurePosixPath('/eval.sh')
        eval_out_docker_path = Path(logger_dir) / 'eval.sh'
        eval_out_docker_path.write_text('\n'.join(eval_cmd_list))
        copy_to_container(container, eval_out_docker_path, eval_path)
        (eval_result, _, _) = exec_run_with_timeout(container, '/bin/bash /eval.sh', timeout=None)
        print(eval_result)
    print(f'copy result for {my_id}')
    with __lock:
        copy_from_container(container, f'/related_methods/{my_id}.json',
                            Path(SWEBENCH_LITE_PREPARE_PATH) / f'related_methods/')
    print(f'copy result success for {my_id}')
    # container.stop(timeout=15)
    # remove_image(client, test_spec.instance_image_key, logger)


if __name__ == '__main__':
    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    # __do_extract(instances[0])
    # for i in instances:
    #     if i['instance_id'] != 'pytest-dev__pytest-5103':
    #         continue
    #     __do_extract(i)
    #     if i['instance_id'] == 'pytest-dev__pytest-5103':
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
