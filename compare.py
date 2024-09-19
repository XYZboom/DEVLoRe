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
    from pyvenn.venn import venn6
    from pyvenn.venn import get_labels

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _debug_eval_path = f"{OUTPUT_PATH}/EvaluateDebug"
    _issue_eval_path = f"{OUTPUT_PATH}/EvaluateIssue"
    _issue_debug_eval_path = f"{OUTPUT_PATH}/EvaluateIssueDebug"
    _eval_path = f"{OUTPUT_PATH}/Evaluate"
    _baseline_debug_eval_path = f"{OUTPUT_PATH}/EvaluateBaselineDebug"
    _baseline_eval_path = f"{OUTPUT_PATH}/EvaluateBaseline"
    _issue_more_count = 0
    _debug_more_count = 0
    _issue_debug_more_count = 0
    _normal_more_count = 0
    _issue_more = set()
    _debug_more = set()
    _issue_debug_more = set()
    _normal_more = set()
    _final = set()
    _exist_final = set()

    venn_data = [set(), set(), set(), set(), set(), set()]
    venn_single_func = [set(), set(), set(), set(a), set(), set()]
    venn_multi_func = [set(), set(), set(), set(), set(), set()]

    for pid, bid in defects4j_utils.d4j_pids_bids():
        _version_str = f"{pid}_{bid}b"
        _debug_eval_file = f"{_debug_eval_path}/{_version_str}.json"
        _issue_eval_file = f"{_issue_eval_path}/{_version_str}.json"
        _issue_debug_eval_file = f"{_issue_debug_eval_path}/{_version_str}.json"
        _eval_file = f"{_eval_path}/{_version_str}.json"
        _baseline_debug_eval_file = f"{_baseline_debug_eval_path}/{_version_str}.json"
        _baseline_eval_file = f"{_baseline_eval_path}/{_version_str}.json"
        _all_eval = [_eval_file, _issue_eval_file, _debug_eval_file,
                     _issue_debug_eval_file, _baseline_eval_file, _baseline_debug_eval_file]


        def add_venn(_file, index):
            if available(_file):
                venn_data[index].add(_version_str)
                if defects4j_utils.is_single_function_bug(pid, bid):
                    venn_single_func[index].add(_version_str)
                else:
                    venn_multi_func[index].add(_version_str)


        for i, _file, in enumerate(_all_eval):
            add_venn(_file, i)
        if available(_baseline_debug_eval_file):
            _final.add((pid, bid))
        if exists(_baseline_debug_eval_file):
            _exist_final.add((pid, bid))
        # for _f in [_debug_eval_file, _issue_eval_file,_issue_debug_eval_file, _eval_file]:
        #     filter_test_edit(_f)
        # continue
        if available(_issue_eval_file) and not available(_eval_file):
            _issue_more_count += 1
            _issue_more.add(_version_str)
        if available(_debug_eval_file) and not available(_eval_file):
            _debug_more_count += 1
            _debug_more.add(_version_str)
        if available(_issue_debug_eval_file) and not available(_eval_file):
            _issue_debug_more_count += 1
            _issue_debug_more.add(_version_str)
        if (available(_eval_file)
                and not available(_debug_eval_file)
                and not available(_issue_debug_eval_file)
                and not available(_issue_eval_file)):
            _normal_more_count += 1
            _normal_more.add(_version_str)

    fig, ax = venn6(get_labels(venn_data),
                    names=['No extra', 'Issue', 'Debug', 'Issue+Debug', 'Perfect', 'Perfect+Debug'])
    plt.show()
    fig1, ax1 = venn6(get_labels(venn_single_func),
                      names=['No extra', 'Issue', 'Debug', 'Issue+Debug', 'Perfect', 'Perfect+Debug'])
    plt.show()
    fig2, ax2 = venn6(get_labels(venn_multi_func),
                      names=['No extra', 'Issue', 'Debug', 'Issue+Debug', 'Perfect', 'Perfect+Debug'])
    plt.show()

    print("issue more:")
    print(_issue_more_count)
    print(_issue_more)
    print("debug more:")
    print(_debug_more_count)
    print(_debug_more)
    print("issue and debug more:")
    print(_issue_debug_more_count)
    print(_issue_debug_more)
    print("issue-debug more than issue:")
    _issue_debug_more_issue = _issue_debug_more.difference(_issue_more)
    print(len(_issue_debug_more_issue))
    print(_issue_debug_more_issue)
    print("issue-debug more than debug:")
    _issue_debug_more_debug = _issue_debug_more.difference(_debug_more)
    print(len(_issue_debug_more_debug))
    print(_issue_debug_more_debug)
    print("normal more than all:")
    print(_normal_more_count)
    print(_normal_more)

    _single_function_count = 0
    _exist_single_function_count = 0
    _fixed_single_function_count = 0
    _fixed_non_single_count = 0
    _more_giant = set()
    _giant_more = set()
    for pid, bid in defects4j_utils.d4j_pids_bids():
        if defects4j_utils.is_single_function_bug(pid, bid):
            _single_function_count += 1
            if (pid, bid) in _exist_final:
                _exist_single_function_count += 1
            if (pid, bid) in _final:
                _fixed_single_function_count += 1
                if not defects4j_utils.can_giant_repair_fix(pid, bid):
                    _more_giant.add((pid, bid))
            if defects4j_utils.can_giant_repair_fix(pid, bid) and (pid, bid) not in _giant_more:
                _giant_more.add((pid, bid))
        elif (pid, bid) in _final:
            _fixed_non_single_count += 1
    print(f"single-function all: {_fixed_single_function_count}/{_single_function_count} = "
          f"{_fixed_single_function_count / _single_function_count}")
    print(f"single-function exist: {_fixed_single_function_count}/{_exist_single_function_count} = "
          f"{_fixed_single_function_count / _exist_single_function_count}")
    print(f"non-single: {_fixed_non_single_count}")
    print(f"single-function more giant: {len(_more_giant)}")
    print(_more_giant)
    print(f"giant more: {len(_giant_more)}")
    print(_giant_more)
