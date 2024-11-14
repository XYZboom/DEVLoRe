__all__ = ["load_env"]

import os
import tempfile


def load_env():
    from dotenv import load_dotenv, find_dotenv
    _ = load_dotenv(find_dotenv())
    tempfile.tempdir = os.environ.get("TMPDIR")
