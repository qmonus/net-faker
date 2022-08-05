from __future__ import annotations
import abc
import typing


class Entity(object):
    def __init__(
        self,
        id: Id,
        type: Type,
        data: typing.Optional[Data] = None,
    ) -> None:
        if data is None:
            data = Data(value="")

        if type.value == "directory":
            if data.value != "":
                raise ValueError("Invalid data value: data must be empty")

        self.id = id
        self.type = type
        self.data = data

    def get_name(self) -> str:
        return self.id.value.split("/")[-1]


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


class Type(object):
    def __init__(self, value: typing.Literal["file", "directory"]) -> None:
        self._value: typing.Literal["file", "directory"] = value

    @property
    def value(self) -> typing.Literal["file", "directory"]:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__


class Data(object):
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


class Repository(abc.ABC):
    @abc.abstractmethod
    async def init(
        self,
    ) -> None:
        pass

    @abc.abstractmethod
    async def get(
        self,
        id: Id,
        include_data: bool = True,
    ) -> typing.Optional[Entity]:
        pass

    @abc.abstractmethod
    async def list(
        self,
        id: typing.Union[Id, typing.List[Id], None] = None,
        type: typing.Union[Type, typing.List[Type], None] = None,
        parent_id: typing.Union[Id, typing.List[Id], None] = None,
        recursive: bool = True,
        include_data: bool = True,
    ) -> typing.List[Entity]:
        pass

    @abc.abstractmethod
    async def add(
        self,
        entity: typing.Union[Entity, typing.List[Entity]],
    ) -> None:
        pass

    @abc.abstractmethod
    async def save(
        self,
        entity: typing.Union[Entity, typing.List[Entity]],
    ) -> None:
        pass

    @abc.abstractmethod
    async def update(
        self,
        entity: typing.Union[Entity, typing.List[Entity]],
    ) -> None:
        pass

    @abc.abstractmethod
    async def remove(
        self,
        entity: typing.Union[Entity, typing.List[Entity]],
    ) -> None:
        pass
