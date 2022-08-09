import typing
import sys
import importlib
import logging

logger = logging.getLogger(__name__)


def import_module(module_path: str, reload: bool) -> typing.Any:
    mod = importlib.import_module(module_path)
    if reload:
        importlib.reload(mod)
    return mod


def delete_module(name: str, recursive: bool = False) -> None:
    if name in sys.modules:
        del sys.modules[name]
        logger.info("Module '{}' deleted from sys.modules".format(name))

    if recursive is True:
        target_names = list(sys.modules.keys())
        for target_name in target_names:
            if target_name.startswith("{}.".format(name)):
                del sys.modules[target_name]
                logger.info("Module '{}' deleted from sys.modules".format(target_name))
