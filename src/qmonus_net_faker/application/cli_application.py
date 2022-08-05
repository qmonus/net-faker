import logging
import typing

from . import exceptions
from ..libs import (
    xml_utils,
    str_utils,
    yang,
)
from ..domain import (
    file_domain,
    yang_tree_domain,
)

logger = logging.getLogger(__name__)

YANG_TREE_MAX_SIZE = 2 * 1024 * 1024


class App(object):
    def __init__(
        self,
        file_repo: file_domain.Repository,
    ):
        self._file_repo = file_repo

    async def init(self) -> None:
        logger.info("Initializing...")

        await self._file_repo.init()

    async def build(self, yang_name: str) -> None:
        logger.info("Building YANG tree...")

        # Create yang-tree entity from yang files
        _files = await self._file_repo.list(
            type=file_domain.Type(value="file"),
            parent_id=file_domain.Id(f"/yangs/{yang_name}"),
            include_data=True,
            recursive=False,
        )
        yang_files = [file for file in _files if file.get_name().endswith(".yang")]
        if len(yang_files) == 0:
            raise exceptions.NotFoundError("No YANG files.")

        builder = yang.YangTreeBuilder()
        for yang_file in yang_files:
            builder.add_yang(filename=yang_file.get_name(), text=yang_file.data.value)

        yang_tree = yang_tree_domain.Entity(
            id=yang_tree_domain.Id(value=yang_name),
            yang_tree=yang_tree_domain.YangTree(value=builder.build()),
        )

        # Create file entity
        text: str = xml_utils.to_string(yang_tree.get_xml(), pretty_print=False)
        texts: typing.List[str] = str_utils.split_string(
            string=text, size=YANG_TREE_MAX_SIZE
        )

        files = []
        for index, text in enumerate(texts):
            file = file_domain.Entity(
                id=file_domain.Id(
                    value=f"/yangs/{yang_name}/yang_tree/yang_tree_{index}.part"
                ),
                type=file_domain.Type(value="file"),
                data=file_domain.Data(value=text),
            )
            files.append(file)

        # Save files
        directory = file_domain.Entity(
            id=file_domain.Id(value=f"/yangs/{yang_name}/yang_tree"),
            type=file_domain.Type(value="directory"),
        )
        await self._file_repo.save(entity=directory)

        old_files = await self._file_repo.list(
            parent_id=file_domain.Id(value=f"/yangs/{yang_name}/yang_tree"),
        )
        await self._file_repo.remove(entity=old_files)

        await self._file_repo.add(entity=files)
