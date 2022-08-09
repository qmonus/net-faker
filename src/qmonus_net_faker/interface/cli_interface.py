from ..application import cli_application


class Interface(object):
    def __init__(
        self,
        cli_app: cli_application.App,
    ) -> None:
        self._cli_app = cli_app

    async def init(self) -> None:
        await self._cli_app.init()
        print("Succeeded.")

    async def build(self, yang_name: str) -> None:
        await self._cli_app.build(yang_name=yang_name)
        print("Succeeded.")
