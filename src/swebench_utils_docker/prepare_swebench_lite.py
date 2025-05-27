import os

from dotenv import load_dotenv, find_dotenv

from src.common_utils import record_error_stack

_ = load_dotenv(find_dotenv())
OUTPUT_PATH = os.environ.get('OUTPUT_PATH')
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', default=16))
import docker.errors
import concurrent.futures

from src.swebench_utils_common import RUN_ID
from swebench.harness.constants import SWEbenchInstance
from swebench.harness.docker_build import build_instance_image, build_container, setup_logger, build_env_images
from swebench.harness.docker_utils import *
from swebench.harness.test_spec.test_spec import make_test_spec
from swebench.harness.utils import load_swebench_dataset

if __name__ == '__main__':
    client = docker.from_env(timeout=120)
    instances = load_swebench_dataset('princeton-nlp/SWE-bench_Lite')
    build_env_images(client, instances, max_workers=32)

    @record_error_stack
    def __do_prepare(_instance: SWEbenchInstance):
        my_id = _instance['instance_id']
        client = docker.from_env(timeout=120)
        test_spec = make_test_spec(
            _instance, namespace="swebench"
        )
        logger_dir = Path(OUTPUT_PATH) / 'logs' / my_id
        logger = setup_logger(my_id, logger_dir / f'{my_id}.log')
        print(f'start build_instance_image {my_id}')
        build_instance_image(test_spec, client, logger, True)
        print(f'end build_instance_image {my_id}')
        try:
            container = client.containers.get(test_spec.get_instance_container_name(RUN_ID))
        except docker.errors.NotFound:
            print(f'start build_container {my_id}')
            container = build_container(test_spec, client, RUN_ID, logger, True)
        container.start()
        print(f'finish {my_id}')

    # for instance in instances:
    #     __do_prepare(instance)

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                __do_prepare,
                _i,
            )
            for _i in instances
        ]
    concurrent.futures.wait(futures)
