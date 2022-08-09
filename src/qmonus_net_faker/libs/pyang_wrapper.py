import typing
import optparse
import io

from pyang import (
    repository,
    context,
    plugin,
)


plugin.init()


class MemoryRepository(repository.Repository):
    def __init__(self, yang_map: typing.Any) -> None:
        self._yang_map = yang_map

    def get_modules_and_revisions(self, ctx: typing.Any) -> list[typing.Any]:
        modules: list[typing.Any] = []
        for module_name in self._yang_map:
            rev = None
            handle = module_name
            modules.append((module_name, rev, handle))
        return modules

    def get_module_from_handle(self, handle: typing.Any) -> typing.Any:
        ref = handle
        format = "yang"
        text = self._yang_map[handle]
        return (ref, format, text)


def convert(module_name: str, yang_map: typing.Any) -> str:
    format_map: typing.Any = {}
    optparser = optparse.OptionParser()
    for _plugin in plugin.plugins:
        _plugin.add_output_format(format_map)
        _plugin.add_opts(optparser)
    options, _ = optparser.parse_args([])

    ctx = context.Context(repository=MemoryRepository(yang_map=yang_map))
    ctx.opts = options  # type: ignore

    for _plugin in plugin.plugins:
        _plugin.setup_ctx(ctx)

    emitter = format_map["yin"]
    emitter.setup_fmt(ctx)

    for _plugin in plugin.plugins:
        _plugin.pre_load_modules(ctx)

    module = ctx.add_module(module_name, yang_map[module_name])
    if module is None:
        raise ValueError(f"Invalid yang module: '{module_name}'")

    for _plugin in plugin.plugins:
        _plugin.pre_validate_ctx(ctx, [module])

    ctx.validate()
    module.prune()

    for _plugin in plugin.plugins:
        _plugin.post_validate_ctx(ctx, [module])

    for position, tag, _ in ctx.errors:
        if tag in ("CIRCULAR_DEPENDENCY", "INCOMPLETE_STATEMENT"):
            raise ValueError(f"Invalid yang modules: {position} - {tag}")

    with io.StringIO() as f:
        emitter.emit(ctx, [module], f)
        value = f.getvalue()

    return value
