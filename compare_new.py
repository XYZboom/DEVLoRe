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
    from pyvenn.venn import venn4, venn5, venn2
    from pyvenn.venn import get_labels

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _debug_path = f"{OUTPUT_PATH}/EvaluateBaselineDebug"
    _issue_path = f"{OUTPUT_PATH}/EvaluateBaselineIssue"
    _stack_path = f"{OUTPUT_PATH}/EvaluateBaselineStack"
    _issue_stack_path = f"{OUTPUT_PATH}/EvaluateBaselineIssueStack"
    _issue_debug_path = f"{OUTPUT_PATH}/EvaluateBaselineIssueDebug"
    _issue_stack_debug_path = f"{OUTPUT_PATH}/EvaluateBaselineIssueStackDebug"
    _path = f"{OUTPUT_PATH}/EvaluateBaseline"
    _names = ['No Extra', 'Issue', 'Debug', 'Stack', 'Issue+Stack', 'Issue+Debug', 'Issue+Stack+Debug']
    venn_data = [(lambda: set())() for i in range(7)]
    venn_single_func = [(lambda: set())() for i in range(7)]
    venn_multi_func = [(lambda: set())() for i in range(7)]
    _exist_single_func = [(lambda: set())() for i in range(7)]
    _exist_multi_func = [(lambda: set())() for i in range(7)]
    _giant_set = set()
    _12_single_func_dict = defaultdict(set)

    for pid, bid in defects4j_utils.ori_d4j_pids_bids():
        _version_str = f"{pid}_{bid}b"
        if defects4j_utils.can_giant_repair_fix(pid, bid):
            if defects4j_utils.is_single_function_bug(pid, bid):
                _12_single_func_dict['GiantRepair'].add(_version_str)
            _giant_set.add(_version_str)
        for baseline_name in defects4j_utils.get_baseline_project_names():
            if (defects4j_utils.can_fix(baseline_name, pid, bid)
                    and defects4j_utils.is_single_function_bug(pid, bid)):
                _12_single_func_dict[baseline_name].add(_version_str)
        _file = f"{_path}/{_version_str}.json"
        _debug_file = f"{_debug_path}/{_version_str}.json"
        _issue_file = f"{_issue_path}/{_version_str}.json"
        _stack_file = f"{_stack_path}/{_version_str}.json"
        _issue_stack_file = f"{_issue_stack_path}/{_version_str}.json"
        _issue_debug_file = f"{_issue_debug_path}/{_version_str}.json"
        _issue_stack_debug_file = f"{_issue_stack_debug_path}/{_version_str}.json"
        _baseline_debug_eval_file = f"{_debug_path}/{_version_str}.json"
        _all_eval = [_file, _issue_file, _debug_file, _stack_file,
                     _issue_stack_file, _issue_debug_file, _issue_stack_debug_file]


        def add_venn(_file, index):
            if available(_file):
                venn_data[index].add(_version_str)
                if defects4j_utils.is_single_function_bug(pid, bid):
                    venn_single_func[index].add(_version_str)
                else:
                    venn_multi_func[index].add(_version_str)
            if exists(_file):
                if defects4j_utils.is_single_function_bug(pid, bid):
                    _exist_single_func[index].add(_version_str)
                else:
                    _exist_multi_func[index].add(_version_str)


        for i, _file, in enumerate(_all_eval):
            add_venn(_file, i)

    _final_all_data = set.union(*venn_data)
    _final_single_data = set.union(*venn_single_func)
    _final_multi_data = set.union(*venn_multi_func)
    _final_no_debug = set.union(*(venn_data[0], venn_data[1], venn_data[3], venn_data[4]))
    _final_debug = set.union(*(venn_data[2], venn_data[5]))

    venn2(get_labels([_final_no_debug, _final_debug]), names=['NoDebug', 'Debug'])
    plt.show()

    print(f"final fixed: {len(_final_all_data)}")
    print(f"final single fixed: {len(_final_single_data)}")
    print(f"final multi fixed: {len(_final_multi_data)}")
    _single_count = 489
    _multi_count = 246

    for _name, _single, _multi, _single_all, _multi_all in (
            zip(_names, venn_single_func, venn_multi_func, _exist_single_func, _exist_multi_func)):
        print(f"{_name}: {len(_single)}/{len(_single_all)}={len(_single) / len(_single_all) * 100:.2f}%,"
              f"{len(_multi)}/{len(_multi_all)}={len(_multi) / len(_multi_all) * 100:.2f}%")

    # fig, ax = venn4(get_labels(venn_data[0:4]),
    #                 names=['No extra', 'Issue', 'Debug', 'Stack'])
    # plt.show()
    # fig1, ax1 = venn4(get_labels(venn_single_func[0:4]),
    #                   names=['No extra', 'Issue', 'Debug', 'Stack'])
    # plt.show()
    # fig2, ax2 = venn4(get_labels(venn_multi_func[0:4]),
    #                   names=['No extra', 'Issue', 'Debug', 'Stack'])
    # plt.show()
    #
    # fig3, ax3 = venn4(get_labels([venn_data[1], venn_data[4], venn_data[5], venn_data[6]]),
    #                   names=['Issue', 'Issue+Stack', 'Issue+Debug', 'Issue+Stack+Debug'])
    # plt.show()
    # fig4, ax4 = venn4(get_labels([venn_single_func[1], venn_single_func[4], venn_single_func[5], venn_single_func[6]]),
    #                   names=['Issue', 'Issue+Stack', 'Issue+Debug', 'Issue+Stack+Debug'])
    # plt.show()
    # fig5, ax5 = venn4(get_labels([venn_multi_func[1], venn_multi_func[4], venn_multi_func[5], venn_multi_func[6]]),
    #                   names=['Issue', 'Issue+Stack', 'Issue+Debug', 'Issue+Stack+Debug'])
    # plt.show()

    sorted_12_single_func = sorted(_12_single_func_dict.items(), key=lambda it: -len(it[1]))
    non_top4_12_single_func = set.union(*list(i[1] for i in sorted_12_single_func[4:]))

    _label6_in = [set() for i in range(5)]
    _label6_in[0] = _final_single_data
    _label6_in[1:5] = list(i[1] for i in sorted_12_single_func[:4])
    _names6_in = ['' for i in range(5)]
    _names6_in[0] = 'Ours'
    _names6_in[1:5] = list(i[0] for i in sorted_12_single_func[:4])
    fig6, ax6 = venn5(get_labels(_label6_in), names=_names6_in)
    plt.savefig("topAprs.pdf")
    plt.show()

    _label6_in[4] = non_top4_12_single_func
    _names6_in[4] = 'Others'
    fig7, ax7 = venn5(get_labels(_label6_in), names=_names6_in)
    plt.show()

    # _single_function_count = 0
    # _exist_single_function_count = 0
    # _fixed_single_function_count = 0
    # _fixed_non_single_count = 0
    # _more_giant = set()
    # _giant_more = set()
    # for pid, bid in defects4j_utils.d4j_pids_bids():
    #     if defects4j_utils.is_single_function_bug(pid, bid):
    #         _single_function_count += 1
    #         if (pid, bid) in _exist_final:
    #             _exist_single_function_count += 1
    #         if (pid, bid) in _final:
    #             _fixed_single_function_count += 1
    #             if not defects4j_utils.can_giant_repair_fix(pid, bid):
    #                 _more_giant.add((pid, bid))
    #         if defects4j_utils.can_giant_repair_fix(pid, bid) and (pid, bid) not in _giant_more:
    #             _giant_more.add((pid, bid))
    #     elif (pid, bid) in _final:
    #         _fixed_non_single_count += 1
    # print(f"single-function all: {_fixed_single_function_count}/{_single_function_count} = "
    #       f"{_fixed_single_function_count / _single_function_count}")
    # print(f"single-function exist: {_fixed_single_function_count}/{_exist_single_function_count} = "
    #       f"{_fixed_single_function_count / _exist_single_function_count}")
    # print(f"non-single: {_fixed_non_single_count}")
    # print(f"single-function more giant: {len(_more_giant)}")
    # print(_more_giant)
    # print(f"giant more: {len(_giant_more)}")
    # print(_giant_more)
