import os

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

@record_error_stack
def __do_extract(_instance: SWEbenchInstance):
    my_id = _instance['instance_id']
    _result_path = Path(SWEBENCH_LITE_PREPARE_PATH) / f'failed_test_stacktrace/{my_id}.txt'
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
    print(f'extracting failed_test_stacktrace: {my_id}')
    try:
        container = client.containers.get(test_spec.get_instance_container_name(RUN_ID))
    except docker.errors.NotFound:
        container = build_container(test_spec, client, RUN_ID, logger, True)
    container.start()
    failed_test = " ".join(handle_swe_failed_test(_instance['FAIL_TO_PASS'], repo_name == 'django/django'))
    # silent the extra part of eval bash.
    eval_cmd_list = test_spec.eval_script_list.copy()
    eval_cmd_list[0] = 'exec 3>&1 4>&2\nexec 1>/dev/null 2>&1\n' + eval_cmd_list[0]
    eval_cmd_list[-4] = eval_cmd_list[-4] + '\nexec 1>&3 2>&4'
    eval_cmd_list[-1] = 'exec 3>&1 4>&2\nexec 1>/dev/null 2>&1\n' + eval_cmd_list[-1] + '\nexec 1>&3 2>&4'
    if repo_name == 'django/django':
        eval_cmd_list[-3] = (f'python /testbed/tests/runtests.py -v=0 --noinput --parallel 1 {failed_test} '
                             fr"| sed -e 's/\x1B\[[0-9;]*[a-zA-Z]//g'")
    else:
        eval_cmd_list[-3] = eval_cmd_list[-3] + fr" | sed -e 's/\x1B\[[0-9;]*[a-zA-Z]//g'"
    eval_path = PurePosixPath('/eval.sh')
    eval_out_docker_path = Path(logger_dir) / 'eval.sh'
    eval_out_docker_path.write_text('\n'.join(eval_cmd_list))
    copy_to_container(container, eval_out_docker_path, eval_path)
    (eval_result, _, _) = exec_run_with_timeout(container, '/bin/bash /eval.sh', timeout=None)
    eval_result = eval_result.replace("/testbed/", "")
    print(eval_result)
    with open(_result_path, 'w') as __f:
        __f.write(eval_result)
    print(f'end extract failed_test_stacktrace: {my_id}')


if __name__ == '__main__':
    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    # __do_extract(instances[0])
    # for i in instances:
        # if i['repo'] != 'django/django':
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
