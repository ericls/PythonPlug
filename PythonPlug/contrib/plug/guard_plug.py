from PythonPlug.plug import Plug


class GuardPlug(Plug):
    def __init__(self):
        super().__init__()
        self.cases = []

    async def call(self, conn):
        for predicate, plug in self.cases:
            if predicate(conn):
                return await plug(conn)

    def case(self, predicate):
        def _decorator(plug):
            self.cases.append((predicate, plug))
            return plug

        return _decorator
