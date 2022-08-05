import logging
import typing
import pathlib
import shutil

from ..libs import file_lib
from ..domain import file_domain

logger = logging.getLogger(__name__)


class Repository(file_domain.Repository):
    def __init__(self, dir_path: pathlib.Path):
        self._dir_path = dir_path

    async def init(self) -> None:
        init_files_path = pathlib.Path(__file__).joinpath("../init_files").resolve()
        shutil.copytree(
            src=init_files_path,
            dst=self._dir_path,
            ignore=shutil.ignore_patterns("__pycache__"),
            dirs_exist_ok=True,
        )

    async def get(
        self,
        id: file_domain.Id,
        include_data: bool = True,
    ) -> typing.Optional[file_domain.Entity]:
        entities = await self.list(id=id, include_data=include_data)
        if entities:
            return entities[0]
        else:
            return None

    async def list(
        self,
        id: typing.Union[file_domain.Id, typing.List[file_domain.Id], None] = None,
        type: typing.Union[
            file_domain.Type, typing.List[file_domain.Type], None
        ] = None,
        parent_id: typing.Union[
            file_domain.Id, typing.List[file_domain.Id], None
        ] = None,
        recursive: bool = True,
        include_data: bool = True,
    ) -> typing.List[file_domain.Entity]:
        if id is None:
            ids = None
        else:
            ids = [i.value for i in (id if isinstance(id, list) else [id])]

        if type is None:
            types = None
        else:
            types = [i.value for i in (type if isinstance(type, list) else [type])]

        if parent_id is None:
            parent_ids = None
        else:
            parent_ids = [
                i.value
                for i in (parent_id if isinstance(parent_id, list) else [parent_id])
            ]

        files = list(self._dir_path.glob("**/*"))

        entities = []
        for file in files:
            if file.suffix in [".pyc"]:
                continue

            if file.name in ["__pycache__"]:
                continue

            _id = "/" + file.relative_to(self._dir_path).as_posix()
            _type: typing.Literal["file", "directory"] = (
                "file" if file.is_file() else "directory"
            )

            # filter
            if ids is not None:
                if _id not in ids:
                    continue

            if types is not None:
                if _type not in types:
                    continue

            if parent_ids is not None:
                _match = False
                for _parent_id in parent_ids:
                    if _parent_id == "/":
                        filter_segments = [""]
                    else:
                        filter_segments = _parent_id.split("/")

                    parent_segments = _id.split("/")[:-1]

                    if recursive:
                        if filter_segments == parent_segments[: len(filter_segments)]:
                            _match = True
                            break
                    else:
                        if filter_segments == parent_segments:
                            _match = True
                            break

                if _match is False:
                    continue

            if file.is_file():
                if include_data:
                    data = file.read_text()
                else:
                    data = ""
            else:
                data = ""

            entity = file_domain.Entity(
                id=file_domain.Id(value=_id),
                type=file_domain.Type(value=_type),
                data=file_domain.Data(value=data),
            )
            entities.append(entity)

        return entities

    async def save(
        self,
        entity: typing.Union[file_domain.Entity, typing.List[file_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = entity
        else:
            _entities = [entity]

        for _entity in _entities:
            path = self._get_path(entity=_entity)
            if _entity.type.value == "file":
                path.write_text(_entity.data.value)
            else:
                path.mkdir(exist_ok=True)

    async def add(
        self,
        entity: typing.Union[file_domain.Entity, typing.List[file_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = entity
        else:
            _entities = [entity]

        # Check duplication
        entity_ids = [_entity.id for _entity in _entities]
        results = await self.list(id=entity_ids)
        if results:
            raise ValueError(f"'{results[0].id}' already exists.")

        await self.save(entity=_entities)

    async def update(
        self,
        entity: typing.Union[file_domain.Entity, typing.List[file_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = entity
        else:
            _entities = [entity]

        # Check if file exists
        entity_ids = [entity.id for entity in _entities]
        existing_entities = await self.list(id=entity_ids)
        if len(_entities) != len(existing_entities):
            raise ValueError("Some entities do not exist.")

        await self.save(entity=_entities)

    async def remove(
        self,
        entity: typing.Union[file_domain.Entity, typing.List[file_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = entity
        else:
            _entities = [entity]

        for _entity in _entities:
            path = self._get_path(entity=_entity)
            file_lib.delete(path=path)

    def _get_path(self, entity: file_domain.Entity) -> pathlib.Path:
        path_str = entity.id.value.lstrip("/")
        path = self._dir_path.joinpath(path_str)
        return path
