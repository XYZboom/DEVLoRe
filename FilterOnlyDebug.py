if __name__ == '__main__':
    import json
    import os
    import re
    from tqdm import tqdm
    import traceback
    import subprocess

    import defects4j_utils

    from dotenv import load_dotenv, find_dotenv
    from Evaluate import do_patch

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _patch_debug_path = f"{OUTPUT_PATH}/PatchDebugInfo"
    _eval_path = f"{OUTPUT_PATH}/Evaluate"
    _debug_eval_path = f"{OUTPUT_PATH}/EvaluateDebug"

    for pid, bid in tqdm(defects4j_utils.d4j_pids_bids()):
        _version_str = f"{pid}_{bid}b"
        _eval_file = f"{_eval_path}/{_version_str}.json"
        _debug_eval_file = f"{_debug_eval_path}/{_version_str}.json"
        if ((not os.path.exists(_eval_file) or os.path.getsize(_eval_file) == 0)
                and os.path.exists(_debug_eval_file) and os.path.getsize(_debug_eval_file) > 0):
            do_patch(pid, bid, _debug_eval_file, _patch_debug_path)
