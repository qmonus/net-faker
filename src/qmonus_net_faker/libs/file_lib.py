import typing
import pathlib


def create_dir(path: pathlib.Path) -> None:
    if path.is_file():
        raise ValueError("Failed to create directory: '{}' is file".format(str(path)))
    path.mkdir(parents=True, exist_ok=True)


def delete(path: pathlib.Path) -> None:
    if path.is_file():
        path.unlink()
    else:
        for child_path in path.glob("*"):
            delete(child_path)
        path.rmdir()


class DirChecker(object):
    def __init__(
        self,
        path: pathlib.Path,
        glob_pattern: str = "**/*",
    ) -> None:
        self._path = path
        self._glob_pattern = glob_pattern
        self._previous_stat = self.get_current_stat()

    def refresh(self) -> None:
        self._previous_stat = self.get_current_stat()

    def get_current_stat(self) -> dict[str, typing.Any]:
        stat: dict[str, typing.Any] = {}
        for file in self._path.glob(self._glob_pattern):
            stat[str(file)] = file.stat().st_mtime
        return stat

    def is_changed(self) -> bool:
        current_stat = self.get_current_stat()
        if self._previous_stat != current_stat:
            return True
        else:
            return False
