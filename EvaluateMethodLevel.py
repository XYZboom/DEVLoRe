# from matplotlib import pyplot as plt

if __name__ == '__main__':
    # from pyvenn.venn import venn4, venn2, venn3, get_labels
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

    _locate_method_IS = f"{OUTPUT_PATH}/LocateMethodIssueStack"
    _locate_method_S = f"{OUTPUT_PATH}/LocateMethodStack"
    _locate_method_I = f"{OUTPUT_PATH}/LocateMethodIssue"
    _locate_method = f"{OUTPUT_PATH}/LocateMethod"
    _paths = [_locate_method_IS, _locate_method_S, _locate_method_I, _locate_method]
    _single_all_set = [set(), set(), set(), set()]
    _single_available_set = [set(), set(), set(), set()]
    _multi_all_set = [set(), set(), set(), set()]
    _multi_available_set = [set(), set(), set(), set()]
    _all_set = [set(), set(), set(), set()]
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

    # venn4(get_labels(_single_available_set), ['Issue+Stack', 'Issue', 'Stack', 'No extra'])
    # plt.show()
    # venn2(get_labels([_single_available_set[1], _single_available_set[2]]), ['Issue', 'Stack'])
    # plt.show()
    # venn4(get_labels(_multi_available_set), ['Issue+Stack', 'Issue', 'Stack', 'No extra'])
    # plt.show()
    # venn2(get_labels([_multi_available_set[1], _multi_available_set[2]]), ['Issue', 'Stack'])
    # plt.show()
    for _locate_method_path, _mall, _mavailable, _sall, _savailable, _all, _all_available in (
            zip(_paths, _multi_all_set, _multi_available_set, _single_all_set, _single_available_set,
                _all_set, _all_available_set)):
        print(_locate_method_path, len(_mall), len(_mavailable), len(_mavailable) / len(_mall),
              len(_sall), len(_savailable), len(_savailable) / len(_sall),
              len(_all), len(_all_available), len(_all_available) / len(_all))
