class Error(Exception):
    pass


class ConflictError(Error):
    pass


class ForbiddenError(Error):
    pass


class NotFoundError(Error):
    pass


class RelatedResourceNotFoundError(Error):
    pass


class FatalError(Error):
    pass
