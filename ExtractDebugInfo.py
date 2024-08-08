import traceback

KEY_ARGS_USE_SPECIFIED = "args.use.specified"
KEY_ARGS_CLASSES = "args.classes"
KEY_ARGS_METHODS = "args.methods"

if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    import defects4j_utils
    import tempfile
    import os
    import json
    import tqdm
    import eventlet
    from BugAutoFixV1.Project import Project
    from ExtractMethodAndField import handle_raw_response
    import concurrent.futures

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _debug_info_path = f"{OUTPUT_PATH}/DebugInfo"
    if not os.path.exists(_debug_info_path):
        os.makedirs(_debug_info_path)

    def extract_debug_info(pid, bid):
        _version_str = f"{pid}_{bid}b"
        _debug_info_output = f"{_debug_info_path}/{_version_str}.txt"
        if os.path.exists(_debug_info_output):
            print(f"{_version_str} exists, skipping...")
            return
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"checkout {_version_str}")
            defects4j_utils.checkout(pid, bid, temp_dir)
            if not os.path.exists(temp_dir):
                print(f"{_version_str} checkout failed.")
                return
            try:
                project = Project(temp_dir)
            except Exception as e:
                print(f"create project failed: {_version_str}")
                return
            _locate_output_path = f"{OUTPUT_PATH}/LocateMethod/{pid}_{bid}b.json"
            if not os.path.exists(_locate_output_path):
                print(f"{pid}_{bid}b method location not found.")
                return
            with open(_locate_output_path, "r") as _f:
                _locate_json = json.load(_f)
            _raw_response = _locate_json['response']
            _methods_located = handle_raw_response(_raw_response)
            with open(os.path.join(temp_dir, "temp.properties"), "w") as _f:
                _f.write(f"{KEY_ARGS_USE_SPECIFIED}=true\n")
                _f.write(f"{KEY_ARGS_METHODS}={_methods_located}")
            print(f"run test {_version_str}")
            trigger_test_methods = project.trigger_test_methods().split(",")
            for method in trigger_test_methods:
                eventlet.monkey_patch()
                try:
                    with eventlet.Timeout(300):
                        project.run_test(False, method)
                except eventlet.Timeout:
                    print("execution time out")
                    return
            print(f"extract debug info {_version_str}")
            _debug_info = project.raw_debug_info()
            with open(_debug_info_output, "w") as f:
                f.write(_debug_info)
        print(f"{_version_str} done")

    all_ids = list(defects4j_utils.d4j_pids_bids())
    for pid, bid in tqdm.tqdm(all_ids, desc=f"Extract debug info", unit="step"):
        try:
            extract_debug_info(pid, bid)
        except Exception as e:
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