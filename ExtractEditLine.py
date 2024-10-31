if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    import os
    import re
    import json
    import defects4j_utils
    import tqdm
    import traceback

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _edit_line_path = f"{OUTPUT_PATH}/FixEditLine"
    if not os.path.exists(_edit_line_path):
        os.makedirs(_edit_line_path)
    _diff_pattern = re.compile(r"--- a/(.*)\n\+\+\+ b/(.*)\n")
    _diff_split_pattern = re.compile(r"--- a/.*\n\+\+\+ b/.*\n")
    _line_pattern = re.compile(r"@@ -(\d+),(\d+) \+(\d+),(\d+)")

    def do_extract(_pid, _bid):
        _version_str = f"{_pid}_{_bid}b"
        _result_path = f"{_edit_line_path}/{_version_str}.json"
        # if os.path.exists(_result_path):
        # print(f"{_version_str} exists")
        # return
        _patch = defects4j_utils.patch_content(_pid, _bid)
        if _patch is None:
            # print(f"{_version_str} patch failed")
            return
        _matches = re.finditer(_diff_pattern, _patch)
        _diff_split = re.split(_diff_split_pattern, _patch)
        _patch_lines = _patch.splitlines()
        _result = []
        for _match, _diff_content in zip(_matches, _diff_split[1:]):
            _match_text = _match.groups()
            if _match_text[0] != _match_text[1]:
                continue
            _edit_file = _match_text[0]
            _diff_matches = re.finditer(_line_pattern, _diff_content)
            for _diff_match in _diff_matches:
                _diff_match_text = _diff_match.groups()
                # patch text start line
                _start_line = _patch.count("\n", 0, _match.end() + _diff_match.end()) + 1
                #                                   ^^^^^^^^^^^^ match end is for the lines starts with --- and +++
                #                                                  ^^^^^^^^^^^^^^^^^
                #                                                  diff end is counted start from split text
                # patch text end line
                _end_line = _start_line + int(_diff_match_text[3])
                _now = _start_line
                # actual edit in src file start line
                _result_start = -1
                for _line_num in range(_start_line, _start_line + _end_line):
                    if _now >= len(_patch_lines):
                        break
                    _patch_line = _patch_lines[_now]
                    if _patch_line.startswith("-"):
                        _result_start = _now
                        break
                    # d4j patches are reversed, + means remove line from buggy version
                    while _patch_line.startswith("+"):
                        if _now >= len(_patch_lines):
                            break
                        _patch_line = _patch_lines[_now]
                        if _result_start == -1:
                            _result_start = _now
                            break
                        _now += 1
                    if _result_start != -1:
                        break
                    _now += 1
                if _result_start == -1:
                    raise Exception()
                _result_start += int(_diff_match_text[2]) - _start_line
                _result.append([_match_text[0], _result_start, _result_start])  # 兼容性填充
        with open(_result_path, "w") as f:
            json.dump(_result, f)
        # print(f"{_version_str} done")


    all_ids = list(defects4j_utils.d4j_pids_bids())
    for pid, bid in tqdm.tqdm(all_ids, desc=f"Extract edit line", unit="step"):
        try:
            do_extract(pid, bid)
        except Exception as e:
            print(pid, bid)
            traceback.print_exc()
    # with concurrent.futures.ThreadPoolExecutor(
    #         max_workers=4
    # ) as executor:
    #     futures = [
    #         executor.submit(
    #             extract_debug_info,
    #             pid,
    #             bid
    #         )
    #         for pid, bid in defects4j_utils.d4j_pids_bids()
    #     ]
    #     concurrent.futures.wait(futures)
