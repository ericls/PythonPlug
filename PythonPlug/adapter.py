from typing import Optional

from .conn import Conn
from .typing import CoroutineFunction


# pylint: disable=too-few-public-methods
class ASGIAdapter:
    """
    Converts a plug to an ASGI Application
    """

    ConnClass = Conn

    def __init__(self, plug: CoroutineFunction) -> None:
        self.plug = plug

    def __call__(
        self,
        scope: dict,
        receive: Optional[CoroutineFunction] = None,
        send: Optional[CoroutineFunction] = None,
    ):
        handler = self.ASGIHandler(scope, self)
        if receive and send:
            return handler(receive, send, interface=Conn.ASGI3)  # ASGI 3.0
        return handler  # ASGI 2.0

    class ASGIHandler:
        def __init__(self, scope, adapter):
            self.scope = scope
            self.adapter = adapter

        async def __call__(self, receive: CoroutineFunction, send: CoroutineFunction, interface=Conn.ASGI2):
            conn = self.adapter.ConnClass(scope=self.scope, receive=receive, send=send)
            conn.interface = interface
            await self.adapter.plug(conn)
            self.adapter.conn = conn
