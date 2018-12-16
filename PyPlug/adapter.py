from .conn import Conn
from .typing import CoroutineFunction


class ASGIAdapter:  # pylint: disable=too-few-public-methods
    """
    Converts a plug to an ASGI Application
    """
    ConnClass = Conn

    def __init__(self, plug: CoroutineFunction) -> None:
        self.plug = plug

    def __call__(self, scope: dict):
        return self.ASGIHandler(scope, self)

    class ASGIHandler:  # pylint: disable=too-few-public-methods
        def __init__(self, scope, adapter):
            self.scope = scope
            self.adapter = adapter

        async def __call__(self, receive: CoroutineFunction, send: CoroutineFunction):
            conn = self.adapter.ConnClass(scope=self.scope, receive=receive, send=send)
            await self.adapter.plug(conn)
            self.adapter.conn = conn
