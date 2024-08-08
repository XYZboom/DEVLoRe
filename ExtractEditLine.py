
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
    _diff_pattern = re.compile(r"--- a/(.*)\n\+\+\+ b/(.*)\n@@ -(\d+),(\d+) \+(\d+),(\d+)")

    def do_extract(_pid, _bid):
        _version_str = f"{_pid}_{_bid}b"
        _result_path = f"{_edit_line_path}/{_version_str}.json"
        if os.path.exists(_result_path):
            # print(f"{_version_str} exists")
            return
        _patch = defects4j_utils.patch_content(_pid, _bid)
        if _patch is None:
            # print(f"{_version_str} patch failed")
            return
        _matches = re.findall(_diff_pattern, _patch)
        _result = []
        for _match in _matches:
            if _match[0] != _match[1]:
                continue
            _start = int(_match[4])
            _end = _start + int(_match[5])
            _result.append([_match[0], _start, _end])
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