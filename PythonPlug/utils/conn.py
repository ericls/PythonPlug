import json

from PythonPlug.conn import Conn


async def send_json(conn: Conn, data, *, status=None, halt=True):
    conn.put_resp_header("content-type", "application/json")
    return await conn.send_resp(json.dumps(data).encode(), status=status, halt=halt)
