import concurrent.futures
import importlib
import json
import os
import ast
from _ast import FunctionDef
from io import StringIO
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv, find_dotenv

from src.swebench_utils.swebench_utils import swe_pids_bids, swe_failed_test

_ = load_dotenv(find_dotenv())

SWEBENCH_LITE_PREPARE_PATH = os.environ.get("SWEBENCH_LITE_PREPARE_PATH")
TEMP_PATH = os.environ.get("TMPDIR")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", default=16))


def __get_content_from_method_names(_source_root, _related_methods: Dict[str, List[str]]) -> Dict[str, str]:
    __r = dict()
    for _file_name in _related_methods:
        _path = Path(_source_root) / _file_name
        _tree = ast.parse(open(_path, 'r').read())
        _methods = _related_methods[_file_name]
        _need_content_ranges = []

        class MethodVisitor(ast.NodeVisitor):
            def __init__(self):
                self.stack = []

            def visit(self, node):
                if len(self.stack) == 0:
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        start_line = node.lineno
                        end_line = node.end_lineno
                        _need_content_ranges.append({
                            'top': True,
                            "start": start_line,
                            "end": end_line,
                        })
                self.stack.append(node)
                super().visit(node)
                assert self.stack.pop() is node

            def visit_FunctionDef(self, node: FunctionDef):
                start_line = node.lineno
                end_line = node.end_lineno
                _need_content_ranges.append({
                    'top': False,
                    "name": node.name,
                    "start": start_line - 1,  # expand for getting more context
                    "end": start_line + 1,
                })

        MethodVisitor().visit(_tree)
        __content = StringIO()
        _lines = open(_path, 'r').readlines()
        for i, line in enumerate(_lines):
            if len(line) == 0:
                continue

            def _can_write(_content_range):
                return (_content_range['start'] <= i <= _content_range['end'] and
                        (_content_range['top'] or _content_range["name"] in _methods)
                        )

            if any(map(_can_write, _need_content_ranges)):
                __content.write(f'{i}|{line}')
        __r[_file_name] = __content.getvalue()
    return __r


def __do_extract(_pid, _bid):
    _source_root = Path(SWEBENCH_LITE_PREPARE_PATH) / f'bugs/{_pid}_{_bid}b'
    _related_method_path = Path(SWEBENCH_LITE_PREPARE_PATH) / f'related_methods/{_pid}_{_bid}b.json'
    _save_to = Path(SWEBENCH_LITE_PREPARE_PATH) / f'related_methods_skeleton/{_pid}_{_bid}b.json'
    if not _save_to.parent.exists():
        _save_to.parent.mkdir(exist_ok=True)
    if not _related_method_path.exists():
        print(f'{_pid}_{_bid}b not exists')
        return
    with open(_related_method_path, 'r') as _f:
        _related_methods = json.load(_f)
    _content_dict = __get_content_from_method_names(_source_root, _related_methods)

    with open(_save_to, 'w') as _f:
        json.dump(_content_dict, _f)


if __name__ == '__main__':
    # for pid, bid in swe_pids_bids():
    #     if pid != 'django' or bid != 0:
    #         continue
    #     __do_extract(pid, bid)
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
