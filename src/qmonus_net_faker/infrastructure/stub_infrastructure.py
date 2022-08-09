import logging
import typing
import copy

from ..domain import stub_domain

logger = logging.getLogger(__name__)


class Repository(stub_domain.Repository):
    def __init__(self) -> None:
        self._entity_map: typing.Dict[str, stub_domain.Entity] = {}

    async def get(
        self,
        id: stub_domain.Id,
    ) -> typing.Optional[stub_domain.Entity]:
        stubs = await self.list(id=id)
        if stubs:
            return stubs[0]
        else:
            return None

    async def list(
        self,
        id: typing.Union[stub_domain.Id, typing.List[stub_domain.Id], None] = None,
    ) -> typing.List[stub_domain.Entity]:
        if id is None:
            ids = None
        else:
            ids = [i.value for i in (id if isinstance(id, list) else [id])]

        entities = []
        for entity_id, entity in self._entity_map.items():
            if ids is not None:
                if entity_id not in ids:
                    continue
            entities.append(copy.deepcopy(entity))

        return entities

    async def save(
        self,
        entity: typing.Union[stub_domain.Entity, typing.List[stub_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = entity
        else:
            _entities = [entity]

        for _entity in _entities:
            self._entity_map[_entity.id.value] = copy.deepcopy(_entity)

    async def add(
        self,
        entity: typing.Union[stub_domain.Entity, typing.List[stub_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = entity
        else:
            _entities = [entity]

        for _entity in _entities:
            if _entity.id.value in self._entity_map:
                raise ValueError(f"'{_entity.id.value}' already exists.")

        await self.save(entity=_entities)

    async def update(
        self,
        entity: typing.Union[stub_domain.Entity, typing.List[stub_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = copy.deepcopy(entity)
        else:
            _entities = [copy.deepcopy(entity)]

        for _entity in _entities:
            if _entity.id.value not in self._entity_map:
                raise ValueError(f"'{_entity.id.value}' does not exist.")

        await self.save(entity=_entities)

    async def remove(
        self,
        entity: typing.Union[stub_domain.Entity, typing.List[stub_domain.Entity]],
    ) -> None:
        if isinstance(entity, list):
            _entities = copy.deepcopy(entity)
        else:
            _entities = [copy.deepcopy(entity)]

        for _entity in _entities:
            if _entity.id.value not in self._entity_map:
                raise ValueError(f"'{_entity.id.value}' does not exist.")

        for _entity in _entities:
            del self._entity_map[_entity.id.value]

    async def remove_all(self) -> None:
        entities = await self.list()
        await self.remove(entity=entities)
