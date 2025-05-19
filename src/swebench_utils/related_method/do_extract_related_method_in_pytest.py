import argparse
import json
import os.path
import runpy
import sys
import threading
from collections import defaultdict
from functools import reduce
from types import FrameType
from typing import List, Dict, Set
import trace

from src.common_utils import file_names_to_tree


class PytestTrace:

    def __enter__(self):
        sys.settrace(self.trace_calls)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.settrace(None)
        # for k in self.recorded_file_methods:
        #     with open(f'{self.save_file_name}_{k}', 'w') as __f:
        #         __f.write('\n'.join(self.recorded_file_methods[k]))
        if len(self.recorded_methods) == 0:
            return
        with open(self.save_file_name, 'w') as __f:
            json.dump({k: list(self.recorded_methods[k]) for k in self.recorded_methods}, __f)

    def __init__(self, save_file: str, allow_files: List[str], test_names: List[str]):
        _parent_path = os.path.abspath(os.path.join(save_file, os.pardir))
        if not os.path.exists(_parent_path):
            os.makedirs(_parent_path)
        self.save_file_name = save_file
        self.allow_files = allow_files
        # key: test method name; value: test method related files
        self.recorded_files: Dict[str, Set[str]] = defaultdict(set)
        # key: file name; value: test method related methods in this file
        self.recorded_methods: Dict[str, Set[str]] = defaultdict(set)
        self.recorded_file_methods: Dict[str, Set[str]] = defaultdict(set)
        self.test_names = test_names
        self.test_method_now: str | None = None

    def trace_calls(self, frame: FrameType, _event: str, args):
        file_name = frame.f_code.co_filename
        func_name = frame.f_code.co_name
        lineno = frame.f_lineno
        allow_record = any(map(lambda _f_name: file_name.startswith(_f_name), self.allow_files))
        if 'site-packages' in file_name or 'test' in file_name:
            allow_record = False
        elif func_name.startswith('<') and func_name.endswith('>'):
            allow_record = func_name == '<module>'
        # if allow_record:
        #     print(file_name, func_name, lineno, _event)
        enter_test = any(map(lambda _method_name: _method_name.split('::')[-1] == func_name, self.test_names))
        if enter_test:
            if _event == 'call':
                # print(f'inside test: {self.test_method_now}', threading.current_thread().name)
                if not self.test_method_now:
                    # print('enter test', file_name, func_name, lineno)
                    self.test_method_now = func_name
            elif _event == 'return':
                if self.test_method_now == func_name:
                    # print('exit test', file_name, func_name, lineno)
                    self.test_method_now = None
        if not self.test_method_now:
            return
        if allow_record:
            # print(file_name, func_name, lineno, _event)
            self.recorded_files[self.test_method_now].add(file_name)
            self.recorded_file_methods[self.test_method_now].add(file_name + ' ---- ' + func_name)
            self.recorded_methods[file_name].add(func_name)
        return self.trace_calls


if __name__ == '__main__':
    print("==========================")
    print(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("script", help="the path to script")
    parser.add_argument("work_dir", help="the path to run seaborn tests")
    parser.add_argument("save_file", help="the file to save results")
    parser.add_argument("-f", "-file", nargs="*", help="filter files")
    parser.add_argument("-args", nargs="*", help="the args passed to the script")
    parsed_args = parser.parse_args()

    mock_args = ["", "-n", "0", "--no-cov", '--no-header'] + parsed_args.args

    original_argv = sys.argv.copy()
    _work_dir = parsed_args.work_dir
    os.chdir(_work_dir)
    os.environ['PWD'] = _work_dir
    os.environ['OLDPWD'] = os.path.dirname(_work_dir)
    sys.argv = mock_args
    sys.path.insert(0, _work_dir)
    globals_dict = {
        "__file__": parsed_args.script,
        "__name__": "__main__",
        "__package__": None,
        '__cached__': None,
        '__builtins__': __builtins__,
    }
    with open(parsed_args.script, 'r') as f:
        import pytest

        with PytestTrace(parsed_args.save_file, parsed_args.f, parsed_args.args):
            pytest.main()
            # exec(f.read())
    sys.argv = original_argv
