class Error(Exception):
    pass


class FatalError(Error):
    pass


class ValidationError(Error):
    pass


class NotFoundError(Error):
    pass


class InputValueError(Error):
    pass


class InputTypeError(Error):
    pass


class NetworkError(Error):
    pass
