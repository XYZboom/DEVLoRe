
if __name__ == '__main__':
    import os
    import json
    import tqdm

    import defects4j_utils

    from dotenv import load_dotenv, find_dotenv

    _ = load_dotenv(find_dotenv())
    D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
    D4J_JSON_PATH = os.environ.get("D4J_JSON_PATH")
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")
    _locate_line_debug_path = f"{OUTPUT_PATH}/LocateLineDebug"
    _locate_line_path = f"{OUTPUT_PATH}/LocateLine"
    _filtered_output_path = f"{OUTPUT_PATH}/LocateLineDebugFiltered"

    if not os.path.exists(_filtered_output_path):
        os.makedirs(_filtered_output_path)

    _all_pb = list(defects4j_utils.d4j_pids_bids())
    _count_decreased = 0
    _all_same = []
    for pid, bid in tqdm.tqdm(_all_pb, desc="Filter debug info"):
        _version_str = f"{pid}_{bid}b"
        _debug_file = f"{_locate_line_debug_path}/{_version_str}.json"
        _non_debug_file = f"{_locate_line_path}/{_version_str}.json"
        if not os.path.exists(_debug_file):
            continue
        if not os.path.exists(_non_debug_file):
            with open(_debug_file, "r") as f:
                with open(_filtered_output_path, "w") as f1:
                    f1.write(f.read())
            continue
        with open(_debug_file, "r") as f:
            _debug_json = json.load(f)
        with open(_non_debug_file, "r") as f:
            _non_debug_json = json.load(f)
        _debug_line = set(i.replace(" ", "") for i in _debug_json['responses'])
        _non_debug_line = set(i.replace(" ", "") for i in _non_debug_json['responses'])
        _filtered_debug_line = _debug_line.difference(_non_debug_line)
        if not _debug_line:
            continue
        _debug_json['responses'] = list(_filtered_debug_line)
        if len(_filtered_debug_line) < len(_debug_line):
            _count_decreased += 1
        if len(_filtered_debug_line) == 0:
            _all_same.append(_version_str)

        with open(f"{_filtered_output_path}/{_version_str}.json", "w") as f:
            json.dump(_debug_json, f)
    print(_count_decreased)
    print("\n".join(_all_same), len(_all_same))
