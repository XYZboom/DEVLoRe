if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    import os
    import re
    import json
    import defects4j_utils
    import argparse
    import tqdm
    import traceback
    from ExtractMethodAndField import handle_raw_response

    parser = argparse.ArgumentParser()
    parser.add_argument("--add-debug-info", help="add debug info", default=False)
    parser.add_argument("--add-issue-info", help="add issue info", default=False)
    args = parser.parse_args()

    _add_debug = args.add_debug_info
    _add_issue = args.add_issue_info

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
    if _add_issue:
        _locate_method_path = f"{OUTPUT_PATH}/LocateMethodIssue"
    else:
        _locate_method_path = f"{OUTPUT_PATH}/LocateMethod"
    _patch_method_path = f"{OUTPUT_PATH}/PatchMethodLocations"
    all_ids = list(defects4j_utils.d4j_pids_bids())

    all_count = 0
    negative_count = 0

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
            all_count += 1
            with open(_patch_method_file, "r") as _f:
                _ground = set(_f.read().splitlines())
            with open(_locate_method_file, "r") as _f:
                _raw = json.load(_f)
                _gpt = set(handle_raw_response(_raw['response']).split(","))
            if _ground.intersection(_gpt):
                negative_count += 1
        except Exception as e:
            print(pid, bid)
            traceback.print_exc()
    print(all_count, negative_count, negative_count / all_count)
