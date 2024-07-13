__all__ = ["load_env"]


def load_env():
    from dotenv import load_dotenv, find_dotenv
    _ = load_dotenv(find_dotenv())
