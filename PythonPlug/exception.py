class PythonPlugException(Exception):
    pass


class HTTPRequestError(PythonPlugException):
    pass


class HTTPStateError(PythonPlugException):
    pass


class PythonPlugRuntimeError(RuntimeError):
    pass
