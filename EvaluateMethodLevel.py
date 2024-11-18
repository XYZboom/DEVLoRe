from collections import defaultdict
from typing import Set, Dict

from matplotlib import pyplot as plt


def handle_line_response(response: str) -> Dict[str, Set[int]]:
    lines = response.strip().split("\n")
    result: Dict[str, Set[int]] = defaultdict(set)
    class_now = None
    for line in lines:
        if not line.startswith("line"):
            class_now = line.strip()
        else:
            try:
                line_num = int(line.strip().replace("line:", "").strip().split(" ")[0])
            except Exception as e:
                continue
            if class_now is None:
                continue
            result[class_now].add(line_num)
    return result


def file_name2class_name(file_name: str) -> str:
    return (file_name
            .removeprefix("src/main/java/")
            .removeprefix("src/main/java")
            .removeprefix("src/main")
            .removeprefix("src/main/")
            .removeprefix("src/java/")
            .removeprefix("src/java")
            .removeprefix("src/")
            .removeprefix("src")
            .removeprefix("source/")
            .removeprefix("source")
            .removesuffix(".java")
            .replace("/", ".")
            )


def matches(tool_line: Dict[str, Set[int]], baseline_line: Dict[str, Set[int]], looseness: int = 0) -> bool:
    for class_name in baseline_line:
        if class_name not in tool_line:
            return False
        for baseline_line_num in baseline_line[class_name]:
            any_match = False
            for i in range(-looseness, looseness + 1):
                wanted = baseline_line_num + i
                if wanted in tool_line[class_name]:
                    any_match = True
                    break
            if not any_match:
                return False
    return True


if __name__ == '__main__':
    from pyvenn.venn import venn4, venn2, venn3, get_labels
    from dotenv import load_dotenv, find_dotenv
    import os
    import re
    import json
    import defects4j_utils
    import argparse
    import tqdm
    import traceback
    from ExtractMethodAndField import handle_raw_response

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
    _patch_method_path = f"{OUTPUT_PATH}/PatchMethodLocations"
    all_ids = list(defects4j_utils.d4j_pids_bids())
    _all_set = [set(), set(), set(), set()]
    _multi_all_set = [set(), set(), set(), set()]
    _single_all_set = [set(), set(), set(), set()]
    # <editor-fold desc="Method">
    _locate_method_IS = f"{OUTPUT_PATH}/LocateMethodIssueStack"
    _locate_method_S = f"{OUTPUT_PATH}/LocateMethodStack"
    _locate_method_I = f"{OUTPUT_PATH}/LocateMethodIssue"
    _locate_method = f"{OUTPUT_PATH}/LocateMethod"
    _paths = [_locate_method_IS, _locate_method_S, _locate_method_I, _locate_method]
    _single_available_set = [set(), set(), set(), set()]
    _multi_available_set = [set(), set(), set(), set()]
    _all_available_set = [set(), set(), set(), set()]

    for _locate_method_path, _mall, _mavailable, _sall, _savailable, _all, _all_available in (
            zip(_paths, _multi_all_set, _multi_available_set, _single_all_set, _single_available_set,
                _all_set, _all_available_set)):
        for pid, bid in tqdm.tqdm(all_ids, desc=f"Evaluate Method Level", unit="step"):
            try:
                # if not defects4j_utils.is_ori_d4j(pid, bid):
                #     continue
                _version_str = f"{pid}_{bid}b"
                _patch_method_file = f"{_patch_method_path}/{_version_str}.txt"
                _locate_method_file = f"{_locate_method_path}/{_version_str}.json"
                if (not os.path.exists(_locate_method_file)
                        or not os.path.exists(_patch_method_file)):
                    continue
                if os.path.getsize(_patch_method_file) == 0:
                    continue
                _all.add((pid, bid))
                if defects4j_utils.is_single_function_bug(pid, bid):
                    _sall.add((pid, bid))
                else:
                    _mall.add((pid, bid))
                with open(_patch_method_file, "r") as _f:
                    _ground = set(_f.read().splitlines())
                with open(_locate_method_file, "r") as _f:
                    _raw = json.load(_f)
                    _gpt = set(handle_raw_response(_raw['response']).split(","))
                if _ground.intersection(_gpt):
                    _all_available.add((pid, bid))
                    if defects4j_utils.is_single_function_bug(pid, bid):
                        _savailable.add((pid, bid))
                    else:
                        _mavailable.add((pid, bid))
            except Exception as e:
                print(pid, bid, _locate_method_path)
                traceback.print_exc()

    venn4(get_labels(_single_available_set), ['Issue+Stack', 'Issue', 'Stack', 'No extra'])
    # plt.show()
    venn2(get_labels([_single_available_set[1], _single_available_set[2]]), ['Issue', 'Stack'])
    # plt.show()
    venn4(get_labels(_multi_available_set), ['Issue+Stack', 'Issue', 'Stack', 'No extra'])
    # plt.show()
    venn2(get_labels([_multi_available_set[1], _multi_available_set[2]]), ['Issue', 'Stack'])
    # plt.show()
    for _locate_method_path, _mall, _mavailable, _sall, _savailable, _all, _all_available in (
            zip(_paths, _multi_all_set, _multi_available_set, _single_all_set, _single_available_set,
                _all_set, _all_available_set)):
        print(_locate_method_path, len(_mall), len(_mavailable), len(_mavailable) / len(_mall),
              len(_sall), len(_savailable), len(_savailable) / len(_sall),
              len(_all), len(_all_available), len(_all_available) / len(_all))
    # </editor-fold>

    _baseline_buggy_line_path = f"{OUTPUT_PATH}/FixEditLine"
    _line_IS = f"{OUTPUT_PATH}/LocateLineBaselineIssueStack"
    _line_I = f"{OUTPUT_PATH}/LocateLineBaselineIssue"
    _line_S = f"{OUTPUT_PATH}/LocateLineBaselineStack"
    _line_D = f"{OUTPUT_PATH}/LocateLineBaselineDebug"
    _line = f"{OUTPUT_PATH}/LocateLineBaseline"
    _line_ID = f"{OUTPUT_PATH}/LocateLineBaselineIssueDebug"
    _line_ISD = f"{OUTPUT_PATH}/LocateLineBaselineIssueStackDebug"
    _paths = [_line, _line_I, _line_S, _line_D, _line_ID, _line_IS, _line_ISD]
    l_single_exact = [(lambda: set())() for _ in _paths]
    l_multi_exact = [(lambda: set())() for _ in _paths]
    l_exact = [(lambda: set())() for _ in _paths]

    l_single_loose3 = [(lambda: set())() for _ in _paths]
    l_multi_loose3 = [(lambda: set())() for _ in _paths]
    l_loose3 = [(lambda: set())() for _ in _paths]

    l_single_loose5 = [(lambda: set())() for _ in _paths]
    l_multi_loose5 = [(lambda: set())() for _ in _paths]
    l_loose5 = [(lambda: set())() for _ in _paths]

    for _path, lSAllE, lMAllE, lAllE, lSAllE3, lMAllE3, lAllE3, lSAllE5, lMAllE5, lAllE5, in (
            zip(_paths, l_single_exact, l_multi_exact, l_exact,
                l_single_loose3, l_multi_loose3, l_loose3, l_single_loose5, l_multi_loose5, l_loose5)):
        for pid, bid in tqdm.tqdm(all_ids, desc=f"Evaluate Line Level", unit="step"):
            baseline_line_f = f"{_baseline_buggy_line_path}/{pid}_{bid}b.json"
            tool_line_f = f"{_path}/{pid}_{bid}b.json"
            if not os.path.exists(tool_line_f):
                continue
            with open(baseline_line_f, "r") as _f:
                baseline_line_list = json.load(_f)
            with open(tool_line_f, "r") as _f:
                tool_line_content = json.load(_f)
            tool_lines_list = tool_line_content['responses']
            baseline_lines: Dict[str, Set[int]] = defaultdict(set)
            for baseline_line_raw in baseline_line_list:
                try:
                    baseline_lines[file_name2class_name(baseline_line_raw[0])].add(int(baseline_line_raw[1]))
                except Exception as e:
                    continue
            for tool_lines_raw in tool_lines_list:
                tool_lines = handle_line_response(tool_lines_raw)
                if matches(tool_lines, baseline_lines):
                    lAllE.add((pid, bid))
                    if defects4j_utils.is_single_function_bug(pid, bid):
                        lSAllE.add((pid, bid))
                    else:
                        lMAllE.add((pid, bid))
                else:
                    # print(baseline_lines)
                    pass
                if matches(tool_lines, baseline_lines, looseness=3):
                    lAllE3.add((pid, bid))
                    if defects4j_utils.is_single_function_bug(pid, bid):
                        lSAllE3.add((pid, bid))
                    else:
                        lMAllE3.add((pid, bid))
                if matches(tool_lines, baseline_lines, looseness=5):
                    lAllE5.add((pid, bid))
                    if defects4j_utils.is_single_function_bug(pid, bid):
                        lSAllE5.add((pid, bid))
                    else:
                        lMAllE5.add((pid, bid))
    d4j_single = list((pid, bid) for pid, bid in defects4j_utils.ori_d4j_pids_bids()
                      if defects4j_utils.is_single_function_bug(pid, bid))
    d4j_multi = list((pid, bid) for pid, bid in defects4j_utils.ori_d4j_pids_bids()
                     if not defects4j_utils.is_single_function_bug(pid, bid))
    for _path, lSAllE, lMAllE, lAllE, lSAllE3, lMAllE3, lAllE3, lSAllE5, lMAllE5, lAllE5, in (
            zip(_paths, l_single_exact, l_multi_exact, l_exact,
                l_single_loose3, l_multi_loose3, l_loose3, l_single_loose5, l_multi_loose5, l_loose5)):
        print(f"{_path} & exact {len(lSAllE) / len(d4j_single) * 100:.2f}\\% & "
              f"{len(lMAllE) / len(d4j_multi) * 100:.2f}\\% & "
              f"{len(lAllE) / 835 * 100:.2f}\\% \\\\ \n"

              f"\t\tloose3 {len(lSAllE3) / len(d4j_single) * 100:.2f}\\% & "
              f"{len(lMAllE3) / len(d4j_multi) * 100:.2f}\\% & "
              f"{len(lAllE3) / 835 * 100:.2f}\\% \\\\ \n"
              
              f"\t\tloose5 {len(lSAllE5) / len(d4j_single) * 100:.2f}\\% & "
              f"{len(lMAllE5) / len(d4j_multi) * 100:.2f}\\% & "
              f"{len(lAllE5) / 835 * 100:.2f}\\% \\\\")
    print(
        f"total & exact {len(set.union(*l_single_exact)) / len(d4j_single) * 100:.2f}\\% & "
        f"{len(set.union(*l_multi_exact)) / len(d4j_multi) * 100:.2f}\\% & "
        f"{len(set.union(*l_exact)) / 835 * 100:.2f}\\% \\\\ \n"
        
        f"\t\tloose3 {len(set.union(*l_single_loose3)) / len(d4j_single) * 100:.2f}\\% & "
        f"{len(set.union(*l_multi_loose3)) / len(d4j_multi) * 100:.2f}\\% & "
        f"{len(set.union(*l_loose3)) / 835 * 100:.2f}\\% \\\\ \n"
        
        f"\t\tloose5 {len(set.union(*l_single_loose5)) / len(d4j_single) * 100:.2f}\\% & "
        f"{len(set.union(*l_multi_loose5)) / len(d4j_multi) * 100:.2f}\\% & "
        f"{len(set.union(*l_loose5)) / 835 * 100:.2f}\\% \\\\ ")
