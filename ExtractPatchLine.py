import traceback

if __name__ == '__main__':
    import os
    import concurrent.futures
    import tqdm
    import subprocess
    import defects4j_utils
    import tempfile

    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _edit_line_path = f"{OUTPUT_PATH}/FixEditLine"
    _patch_method_path = f"{OUTPUT_PATH}/PatchMethodLocations"
    if not os.path.exists(_patch_method_path):
        os.makedirs(_patch_method_path)
    locator_jar = "/home/xyzboom/jars/MethodLocator-1.0-SNAPSHOT-all.jar"


    def locate(_input, _output, _location):
        _process = subprocess.Popen(["java", "-XX:ReservedCodeCacheSize=2G",
                                     "-Xmx4g", "-Xms4g",
                                     "-Djava.awt.headless=true",
                                     "-jar", locator_jar, "-i", _input, "-o", _output, "-l", _location])
        _out, _err = _process.communicate()
        if _out:
            print(_out.decode())
        if _err:
            print(_err.decode())


    def doit(_pid, _bid):
        _v = f"{_pid}_{_bid}b"
        _e = f"{_edit_line_path}/{_v}.json"
        _o = f"{_patch_method_path}/{_v}.txt"
        if os.path.exists(_o):
            print(f"{_v} exists")
            return
        with tempfile.TemporaryDirectory() as tmp:
            print(f"checkout: {_v}")
            defects4j_utils.checkout(_pid, _bid, tmp)
            if not os.path.exists(tmp):
                print(f"checkout failed: {_v}")
                return
            locate(tmp, _o, _e)
        print(f"done {_v}")


    all_ids = list(defects4j_utils.d4j_pids_bids())
    # for pid, bid in tqdm.tqdm(all_ids, desc=f"Extract edit line", unit="step"):
    #     try:
    #         doit(pid, bid)
    #     except Exception as e:
    #         print(pid, bid)
    #         traceback.print_exc()
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=64
    ) as executor:
        futures = [
            executor.submit(
                doit,
                pid,
                bid
            )
            for pid, bid in all_ids
        ]
        concurrent.futures.wait(futures)
