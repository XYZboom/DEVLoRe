import os
import traceback
from collections import defaultdict
from typing import Set, Dict, Union, List, Iterable
from io import StringIO


def record_error_stack(func):
    def inner_func(*arg, **kwargs):
        # noinspection PyBroadException
        try:
            func(*arg, **kwargs)
        except:
            traceback.print_exc()

    return inner_func


FileTree = Dict[str, List[Union['FileTree', str]]]


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


if __name__ == '__main__':
    # 示例文件名列表
    file_list = [
        '/path/to/file1.txt',
        '/path/to/folder1/file2.txt',
        '/path/to/folder1/folder2/file3.txt',
        '/path/to/folder1/file3.txt'
    ]

    result = file_names_to_tree(file_list)
    print(result)
