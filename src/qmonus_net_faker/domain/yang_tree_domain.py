from __future__ import annotations
import abc
import typing

from ..libs import yang


class Entity(object):
    def __init__(
        self,
        id: Id,
        yang_tree: YangTree,
    ) -> None:
        self.id = id
        self.yang_tree = yang_tree

    def get_xml(self) -> typing.Any:
        return self.yang_tree.value.get_xml()

    def get_root_node(self) -> typing.Any:
        return self.yang_tree.value.get_root_node()

    def validate(self, config: typing.Any) -> None:
        self.yang_tree.value.validate(config=config)


class Id(object):
    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class YangTree(object):
    def __init__(self, value: yang.YangTree) -> None:
        self._value = value

    @property
    def value(self) -> yang.YangTree:
        return self._value

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class Repository(abc.ABC):
    @abc.abstractmethod
    async def get(self, id: Id) -> typing.Optional[Entity]:
        pass

    @abc.abstractmethod
    async def list(
        self, id: typing.Union[Id, typing.List[Id], None] = None
    ) -> typing.List[Entity]:
        pass

    @abc.abstractmethod
    async def save(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def add(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def remove(self, entity: typing.Union[Entity, typing.List[Entity]]) -> None:
        pass

    @abc.abstractmethod
    async def remove_all(self) -> None:
        pass
