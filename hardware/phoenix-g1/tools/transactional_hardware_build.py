"""Restore generated design outputs if a build or verification step fails."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile


@contextmanager
def preserve_outputs(paths):
    paths = [Path(path) for path in paths]
    with tempfile.TemporaryDirectory(prefix='phoenix-build-checkpoint-') as temp:
        backups = []
        for index, path in enumerate(paths):
            saved = Path(temp)/str(index)
            existed = path.exists()
            if existed:
                shutil.copytree(path, saved)
            backups.append((path, saved, existed))
        try:
            yield
        except BaseException:
            for path, saved, existed in backups:
                if path.exists():
                    shutil.rmtree(path)
                if existed:
                    shutil.copytree(saved, path)
            raise
