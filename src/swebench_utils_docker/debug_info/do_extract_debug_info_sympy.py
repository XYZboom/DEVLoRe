import argparse
import json
import os.path
import sys
import traceback
from collections import defaultdict
from io import StringIO
from pathlib import Path
from types import FrameType
from typing import List, Set, Iterable, Dict, Tuple


def file_names_to_tree(file_names: Iterable[str]) -> str:
    tree = {}
    for file_path in file_names:
        parts = file_path.split(os.sep)
        current_level = tree

        for part in parts:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]

    def print_dict(d, __result, level=-1):
        for key in d:
            if key != '':
                __result.write('  ' * level + key + '\n')
            print_dict(d[key], __result, level + 1)

    __result = StringIO()
    print_dict(tree, __result)
    return __result.getvalue()


def remove_prefix(__s: str, __prefix: str) -> str:
    if __s.startswith(__prefix):
        return __s[len(__prefix):]
    return __s


class PytestTrace:

    def __enter__(self):
        if not Path(self.save_file_name).parent.exists():
            Path(self.save_file_name).parent.mkdir()
        self.save_file = open(self.save_file_name, 'w')
        sys.settrace(self.trace_calls)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.settrace(None)
        self.save_file.close()

    def remove_prefix(self, file_name: str) -> str:
        _r = file_name
        for allow_file in self.allow_files:
            _r = _r.removeprefix(allow_file)
        return _r

    def __init__(self, save_file: str, allow_files: List[str], test_names: List[str], method_names: List[str]):
        _parent_path = os.path.abspath(os.path.join(save_file, os.pardir))
        if not os.path.exists(_parent_path):
            os.makedirs(_parent_path)
        self.save_file_name = save_file
        self.allow_files = allow_files
        self.test_names = test_names
        self.last_locals: Dict[str, str] = {}
        self.method_names = []
        for __m in method_names:
            if '```' in __m:
                continue
            self.method_names.append(__m.split('::')[-1])

    def trace_calls(self, frame: FrameType, _event: str, args):
        file_name = frame.f_code.co_filename
        func_name = frame.f_code.co_name
        line = frame.f_lineno
        allow_record = any(map(lambda _f_name: file_name.startswith(_f_name), self.allow_files))
        if 'site-packages' in file_name or 'test' in remove_prefix(file_name, '/testbed'):
            allow_record = False
        if func_name.startswith('<') and func_name.endswith('>'):
            allow_record = False
        allow_record = allow_record and func_name in self.method_names

        def safe_str(obj, depth: int = 0) -> str:
            if hasattr(obj, '__dict__') and depth == 0:
                return safe_str(obj.__dict__, depth + 1)
            try:
                return str(obj)
            except:
                return f"<{obj.__class__.__name__} at 0x{id(obj):x}>"

        def filter_var_name(m):
            if m.startswith('__'):
                return False
            if m in ['quit', 'self']:
                return False
            if safe_str(frame.f_locals[m]) == self.last_locals.get(m, None):
                return False
            return True

        if allow_record and _event == 'line':
            _si_all = StringIO()
            try:
                _si_all.write(file_name + '::' + func_name + ":" + str(line) + '\n')
                filtered_locals = {k: frame.f_locals[k] for k in frame.f_locals if filter_var_name(k)}
                self.last_locals = {k: safe_str(frame.f_locals[k]) for k in frame.f_locals}
                if len(filtered_locals) == 0:
                    return self.trace_calls
                # print(filtered_locals)
                _si_all.write(str(filtered_locals))
                _si_all.write('\nvariable types:' + '\n')
                _si = StringIO()
                json.dump({k: str(filtered_locals[k].__class__) for k in filtered_locals}, _si)
                _si_all.write(_si.getvalue())
                _si_all.write('\n')
                _si_all.flush()
            except BaseException:
                # traceback.print_exc()
                pass
            _value = _si_all.getvalue()
            if len(_value) != 0:
                self.save_file.write(_value)
        return self.trace_calls


if __name__ == '__main__':
    print("==========================")
    print(' '.join(sys.argv))
    parser = argparse.ArgumentParser()
    parser.add_argument("script", help="the path to script")
    parser.add_argument("work_dir", help="the path to run seaborn tests")
    parser.add_argument("save_file", help="the file to save results")
    parser.add_argument("-m", nargs='*', help='method to record debug info')
    parser.add_argument("-f", "-file", nargs="*", help="filter files")
    parser.add_argument("-args", nargs="*", help="the args passed to the script")
    parsed_args = parser.parse_args()

    mock_args = ["", "--no-subprocess", "-C", "--verbose"] + parsed_args.args

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
        code = compile(f.read(), parsed_args.script, 'exec')
        with PytestTrace(parsed_args.save_file, parsed_args.f, parsed_args.args, parsed_args.m):
            exec(code, globals_dict)
    sys.argv = original_argv
