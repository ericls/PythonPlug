class PyPlugException(Exception):
    pass


class HTTPRequestError(PyPlugException):
    pass


class HTTPStateError(PyPlugException):
    pass


class PyPlugRuntimeError(RuntimeError):
    pass
