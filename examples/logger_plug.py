import logging
import time

from PythonPlug.conn import Conn
from PythonPlug.plug import Plug


class LoggerPlug(Plug):
    def __init__(self, *, logger=None, level=logging.INFO):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.level = level
        super().__init__()

    async def call(self, conn: Conn):
        conn.private["logger_plug_start_time"] = time.time()
        conn.register_after_start(self.after_start)
        return conn

    async def after_start(self, conn: Conn):
        logging_args = {
            "method": conn.scope.get("method"),
            "path": conn.scope.get("path"),
            "timems": (time.time() - conn.logger_plug_start_time) * 1000,
        }
        self.logger.log(
            self.level, "{method}: {path} ({timems}ms)".format_map(logging_args)
        )
