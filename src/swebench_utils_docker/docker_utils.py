import tarfile
from pathlib import Path

from docker.models.containers import Container


def copy_from_container(container: Container, src: Path | str, dst: Path):
    bits, stat = container.get_archive(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst.with_suffix('._tar'), 'wb') as __f:
        for block in bits:
            __f.write(block)
    with tarfile.open(str(dst.with_suffix('._tar'))) as __f:
        __f.extractall(str(dst))
    dst.with_suffix('._tar').unlink()
