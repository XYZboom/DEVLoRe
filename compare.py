def filter_test_edit(_f: str):
    if not os.path.exists(_f):
        return
    with open(_f, "r") as _ff:
        _s = _ff.read()
    if "test" in _s or "Test" in _s:
        os.remove(_f)


if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    import os
    import defects4j_utils

    _ = load_dotenv(find_dotenv())
    OUTPUT_PATH = os.environ.get("OUTPUT_PATH")

    _debug_eval_path = f"{OUTPUT_PATH}/EvaluateDebug"
    _issue_eval_path = f"{OUTPUT_PATH}/EvaluateIssue"
    _issue_debug_eval_path = f"{OUTPUT_PATH}/EvaluateIssueDebug"
    _eval_path = f"{OUTPUT_PATH}/Evaluate"
    _issue_more_count = 0
    _debug_more_count = 0
    _issue_debug_more_count = 0
    _normal_more_count = 0
    _issue_more = set()
    _debug_more = set()
    _issue_debug_more = set()
    _normal_more = set()

    for pid, bid in defects4j_utils.d4j_pids_bids():
        _version_str = f"{pid}_{bid}b"
        _debug_eval_file = f"{_debug_eval_path}/{_version_str}.json"
        _issue_eval_file = f"{_issue_eval_path}/{_version_str}.json"
        _issue_debug_eval_file = f"{_issue_debug_eval_path}/{_version_str}.json"
        _eval_file = f"{_eval_path}/{_version_str}.json"
        # for _f in [_debug_eval_file, _issue_eval_file,_issue_debug_eval_file, _eval_file]:
        #     filter_test_edit(_f)
        # continue
        if ((os.path.exists(_issue_eval_file) and os.path.getsize(_issue_eval_file) > 0)
                and (not os.path.exists(_eval_file) or os.path.getsize(_eval_file) == 0)):
            _issue_more_count += 1
            _issue_more.add(_version_str)
        if ((os.path.exists(_debug_eval_file) and os.path.getsize(_debug_eval_file) > 0)
                and (not os.path.exists(_eval_file) or os.path.getsize(_eval_file) == 0)):
            _debug_more_count += 1
            _debug_more.add(_version_str)
        if ((os.path.exists(_issue_debug_eval_file) and os.path.getsize(_issue_debug_eval_file) > 0)
                and (not os.path.exists(_eval_file) or os.path.getsize(_eval_file) == 0)):
            _issue_debug_more_count += 1
            _issue_debug_more.add(_version_str)
        if ((os.path.exists(_eval_file) and os.path.getsize(_eval_file) > 0)
                and (not os.path.exists(_debug_eval_file) or os.path.getsize(_debug_eval_file) == 0)
                and (not os.path.exists(_issue_debug_eval_file) or os.path.getsize(_issue_debug_eval_file) == 0)
                and (not os.path.exists(_issue_eval_file) or os.path.getsize(_issue_eval_file) == 0)):
            _normal_more_count += 1
            _normal_more.add(_version_str)

    print("issue:")
    print(_issue_more_count)
    print(_issue_more)
    print("debug:")
    print(_debug_more_count)
    print(_debug_more)
    print("issue and debug:")
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
    print(_normal_more_count)
    print(_normal_more)
