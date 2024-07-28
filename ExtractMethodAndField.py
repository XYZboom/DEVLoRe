import concurrent.futures
import subprocess
import os

import dotenv
from dotenv import load_dotenv, find_dotenv

import defects4j_utils

_ = load_dotenv(find_dotenv())
EXTRACT_JAR_PATH = os.environ.get("EXTRACT_JAR_PATH")


def extract_trigger_test(_path, _members, _output):
    _process = subprocess.Popen(["java", "-jar", EXTRACT_JAR_PATH,
                                 "-i", _path, "-o", _output, "-f", _members, ],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _out, _err = _process.communicate()
    if _err:
        print(_err.decode())
