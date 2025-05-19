import ast
import concurrent.futures
import json
from _ast import FunctionDef
from typing import List, Dict, Literal, TypedDict

import unidiff, os
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv, find_dotenv

from src.common_utils import record_error_stack
from src.swebench_utils.swebench_utils import swe_pids_bids, swe_failed_test

_ = load_dotenv(find_dotenv())

SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
TEMP_PATH = os.environ.get("TMPDIR")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))


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


def get_affected_methods(_patch_file, _source_root) -> Dict[str, List[Method]]:
    _affected_methods = defaultdict(list)
    with open(_patch_file, 'r') as _f:
        patch = unidiff.PatchSet(_f)

    for patched_file in patch:
        _file_path = Path(_source_root) / patched_file.target_file[2:]
        if not _file_path.exists():
            continue

        with open(_file_path, 'r') as src_file:
            _source_code = src_file.read()
        _methods = affect_methods_from_ast(_source_code)

        for hunk in patched_file:
            start_line = hunk.target_start
            end_line = start_line + hunk.target_length - 1

            for _method in _methods:
                if _method['start'] <= start_line <= _method['end'] or \
                        _method['start'] <= end_line <= _method['end']:
                    _affected_methods[str(_file_path)].append(_method)

    return _affected_methods


def extract_method_content(_method: Method, _source_code):
    lines = _source_code.split('\n')
    start_idx = _method['start'] - 1
    end_idx = _method['end']
    return '\n'.join(lines[start_idx:end_idx])


@record_error_stack
def __do_extract(_pid, _bid):
    """
    the following json will be saved
    ```json
    {        'path/to/file_name.py': {
            'method_name': 'extract_method_content',
        }
    }
    ```
    """
    _save_to = Path(SWEBENCH_LITE_PREPARE_PATH) / f"failed_test_content/{_pid}_{_bid}b.json"
    if os.path.exists(_save_to):
        print(f"{_pid}_{_bid} exists")
        return
    _source_root = Path(SWEBENCH_LITE_PREPARE_PATH) / f"bugs/{_pid}_{_bid}b"
    if not os.path.exists(_source_root):
        print(f"{_pid}_{_bid} repo not exists")
        return
    _patch_file = Path(_source_root) / "swebench_test.patch"
    _affected_methods = get_affected_methods(_patch_file, _source_root)
    _result_dict = defaultdict(dict)

    for _file_path, _methods in _affected_methods.items():
        with open(_file_path, 'r') as f:
            _source_code = f.read()

        for _method in _methods:
            _content = extract_method_content(_method, _source_code)
            _result_dict[_file_path.replace(str(_source_root), '')][_method['name']] = _content

    if not _save_to.parent.exists():
        _save_to.parent.mkdir()
    if len(_result_dict) == 0:
        return
    with open(_save_to, 'w') as _f:
        json.dump(_result_dict, _f)


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS
    ) as executor:
        futures = [
            executor.submit(
                __do_extract,
                pid,
                bid
            )
            for pid, bid in swe_pids_bids()
        ]
        concurrent.futures.wait(futures)
