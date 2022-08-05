import typing
import uuid
import re

import jinja2


def generate_uuid() -> str:
    return uuid.uuid4().hex


def normalize_line_ending(string: str, to: str = "\n") -> str:
    new_string = re.sub(r"\r\n|\r|\n", to, string)
    return new_string


def split_string(string: str, size: int) -> list[str]:
    results: list[str] = []
    for i in range(0, len(string), size):
        results.append(string[i : i + size])
    return results


def render(template: str, variables: typing.Any) -> str:
    env = jinja2.Environment(
        loader=jinja2.BaseLoader(),
        undefined=jinja2.StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=False,
    )

    return env.from_string(template).render(variables)
