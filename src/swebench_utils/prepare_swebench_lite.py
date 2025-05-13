import csv
import os

from dotenv import load_dotenv, find_dotenv

from src.git_utils.git_utils import git_clone

_ = load_dotenv(find_dotenv())
SWEBENCH_LITE_REPO_PATH = os.environ.get("SWEBENCH_LITE_REPO_PATH")

if __name__ == '__main__':
    from datasets import load_dataset

    # Login using e.g. `huggingface-cli login` to access this dataset
    ds = load_dataset("SWE-bench/SWE-bench_Lite", split="test")

    repos = set(map(lambda data: data['repo'], ds))
    for repo in repos:
        clone_to = f"{SWEBENCH_LITE_REPO_PATH}/{repo.split('/')[-1]}"
        if os.path.exists(clone_to):
            print(f"{clone_to} already exists")
            continue
        git_clone(f"https://github.com/{repo}", clone_to)
