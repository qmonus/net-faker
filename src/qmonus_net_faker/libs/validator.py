import typing
import jsonschema


class ValidationError(Exception):
    pass


class Validator(object):
    def __init__(self) -> None:
        self._format_checker = jsonschema.FormatChecker(formats={})

    def add_format(self, name: str, func: typing.Callable[[typing.Any], bool]) -> None:
        self._format_checker.checks(format=name)(func)

    def validate(self, value: typing.Any, schema: typing.Any) -> None:
        self.check_schema(schema=schema)
        errors = [
            error
            for error in jsonschema.Draft7Validator(
                schema, format_checker=self._format_checker
            ).iter_errors(value)
        ]
        if errors:
            error = errors[0]
            error_path = ".".join([str(path) for path in list(error.path)])
            if error_path:
                message = f"Invalid request ({error_path}): {error.message}"
            else:
                message = f"Invalid request: {error.message}"
            raise ValidationError(message)

    def check_schema(self, schema: typing.Any) -> None:
        format_names = []
        whole_schema = schema

        def _extract(_schema: typing.Any) -> None:
            if "$ref" in _schema:
                ref = _schema["$ref"]
                ref_parts = ref.split("/")[1:]

                target_schema = whole_schema
                for ref_part in ref_parts:
                    target_schema = target_schema[ref_part]
                _extract(target_schema)
            if "format" in _schema:
                format_names.append(_schema["format"])
            if "type" in _schema:
                if _schema["type"] == "array":
                    if "items" in _schema:
                        _extract(_schema["items"])
                elif _schema["type"] == "object":
                    if "properties" in _schema:
                        for _property, _property_schema in _schema[
                            "properties"
                        ].items():
                            _extract(_property_schema)

        _extract(schema)

        unknown_format_names = set(format_names) - set(
            [_name for _name in self._format_checker.checkers.keys()]
        )
        if len(unknown_format_names) > 0:
            raise ValueError(
                "Unknown format '{}' specified".format(unknown_format_names.pop())
            )
