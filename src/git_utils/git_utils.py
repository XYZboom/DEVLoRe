import git
from tqdm import tqdm


class GitCloneProgress(git.remote.RemoteProgress):

    def __init__(self, progress_bar):
        super().__init__()
        self.progress_bar = progress_bar

    def update(self, op_code, cur_count, max_count=None, message=''):
        if max_count is not None:
            self.progress_bar.total = max_count
            self.progress_bar.update(cur_count - self.progress_bar.n)


def git_clone(url: str, to_path: str, desc: str = None) -> git.Repo:
    if desc is None:
        desc = f"clone from {url} to {to_path}"
    progress_bar = tqdm(desc=desc, total=100, unit='B', unit_scale=True)
    # noinspection PyTypeChecker
    __r = git.Repo.clone_from(url, to_path, progress=GitCloneProgress(progress_bar))
    progress_bar.close()
    return __r
