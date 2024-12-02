from typing import Dict, List

import matplotlib.pyplot as plt


def filter_test_edit(_f: str):
    if not os.path.exists(_f):
        return
    with open(_f, "r") as _ff:
        _s = _ff.read()
    if "test" in _s or "Test" in _s:
        os.remove(_f)


def available(_path: str) -> bool:
    return os.path.exists(_path) and os.path.getsize(_path) > 0


def exists(_path: str) -> bool:
    return os.path.exists(_path)


if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    import os
    import defects4j_utils
    from collections import defaultdict
    from pyvenn.venn import venn5
    from pyvenn.venn import get_labels

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _eval = f"{OUTPUT_PATH}/Evaluate"
    _evalI = f"{OUTPUT_PATH}/EvaluateIssue"
    _evalD = f"{OUTPUT_PATH}/EvaluateDebug"
    _evalS = f"{OUTPUT_PATH}/EvaluateStack"
    _evalID = f"{OUTPUT_PATH}/EvaluateIssueDebug"
    _evalIS = f"{OUTPUT_PATH}/EvaluateIssueStack"
    _evalSD = f"{OUTPUT_PATH}/EvaluateStackDebug"
    _evalISD = f"{OUTPUT_PATH}/EvaluateIssueStackDebug"
    _paths = [_eval, _evalI, _evalD, _evalS, _evalID, _evalIS, _evalSD, _evalISD]
    _names = ["No extra", "Issue", "Debug", "Stack", "Issue+Debug", "Issue+Stack", "Stack+Debug", "Issue+Stack+Debug"]
    _multi_count = 0
    _single_count = 0
    _all_count = 0
    # range(6) here is {single, multi, all} x {available, all},
    _eval_map: Dict[str, List[set]] = {i: [(lambda: set())() for _ in range(6)] for i in _names}
    for pid, bid in defects4j_utils.ori_d4j_pids_bids():
        is_single = defects4j_utils.is_single_function_bug(pid, bid)
        _all_count += 1
        if is_single:
            _single_count += 1
        else:
            _multi_count += 1
        for _path, _name in zip(_paths, _names):
            single, single_all, multi, multi_all, _all, _all_all = _eval_map[_name]
            _version_str = f"{pid}_{bid}b"
            _eval_file = f"{_path}/{_version_str}.json"
            if not os.path.exists(_eval_file):
                continue
            _all_all.add(_version_str)
            if is_single:
                single_all.add(_version_str)
            else:
                multi_all.add(_version_str)
            if os.path.getsize(_eval_file) != 0:
                _all.add(_version_str)
                if is_single:
                    single.add(_version_str)
                else:
                    multi.add(_version_str)

    union = [set.union(*[_eval_map[k][0] for k in _eval_map]),
             set.union(*[_eval_map[k][2] for k in _eval_map]),
             set.union(*[_eval_map[k][4] for k in _eval_map])]

    for _name in _names:
        single, single_all, multi, multi_all, _all, _all_all = _eval_map[_name]
        print(f"{_name} & {len(single)}/{len(single_all)}={len(single) / len(single_all) * 100:.1f}\\% "
              f"& {len(multi)}/{len(multi_all)}={len(multi) / len(multi_all) * 100:.1f}\\% "
              f"& {len(_all)}/{len(_all_all)}={len(_all) / len(_all_all) * 100:.1f}\\% \\\\")
    print(f"Union & {len(union[0])}/{_single_count}={len(union[0]) / _single_count * 100:.1f}\\% "
          f"& {len(union[1])}/{_multi_count}={len(union[1]) / _multi_count * 100:.1f}\\% "
          f"& {len(union[2])}/{_all_count}={len(union[2]) / _all_count * 100:.1f}\\% \\\\")
    _labels = get_labels([_eval_map[k][4] for k in ["Issue", "Debug", "Stack", "Issue+Debug", "Issue+Stack"]])
    print(_labels)
    venn5(_labels,
          ["Issue", "Debug", "Stack", "Issue+Debug", "Issue+Stack"],
          dpi=96, fontsize=24, figsize=(18, 12), legend_loc='right')
    plt.savefig(f"{OUTPUT_PATH}/Overall_overlap.pdf")
    plt.show()
