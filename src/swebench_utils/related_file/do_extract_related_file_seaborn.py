import argparse
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


class SeabornTrace:

    def __enter__(self):
        sys.settrace(self.trace_calls)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.settrace(None)
        if len(self.recorded_files) == 0:
            return
        with open(self.save_file_name, 'w') as __f:
            __f.write(file_names_to_tree(map(lambda _s: self.remove_prefix(_s), self.recorded_files)))

    def remove_prefix(self, file_name: str) -> str:
        _r = file_name
        for allow_file in self.allow_files:
            _r = _r.removeprefix(allow_file)
        return _r

    def __init__(self, save_file: str, allow_files: List[str], test_names: List[str]):
        _parent_path = os.path.abspath(os.path.join(save_file, os.pardir))
        if not os.path.exists(_parent_path):
            os.makedirs(_parent_path)
        self.save_file_name = save_file
        self.allow_files = allow_files
        self.recorded_files: Set[str] = set()
        self.test_names = test_names

    def trace_calls(self, frame: FrameType, _event: str, args):
        file_name = frame.f_code.co_filename
        func_name = frame.f_code.co_name
        lineno = frame.f_lineno
        allow_record = any(map(lambda _f_name: file_name.startswith(_f_name), self.allow_files))
        if 'site-packages' in file_name or 'test' in file_name:
            allow_record = False
        if func_name.startswith('<') and func_name.endswith('>'):
            allow_record = allow_record and func_name == '<module>'
        if allow_record:
            # print(file_name, func_name, lineno, _event)
            self.recorded_files.add(file_name)
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
        with SeabornTrace(parsed_args.save_file, parsed_args.f, parsed_args.args):
            print(sys.gettrace())
            import pytest
            pytest.main()
            print(sys.gettrace())
            # exec(f.read())
    sys.argv = original_argv
