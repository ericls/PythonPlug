from abc import ABC, abstractmethod
from typing import List


class Plug(ABC):
    plugs: List["Plug"] = []

    def __init__(self):
        pass

    @abstractmethod
    async def call(self, conn):
        "abstract call"

    async def __call__(self, conn):
        for plug in self.plugs:
            await plug(conn)
            if conn.halted:
                return conn
        return await self.call(conn)
