import json

from PythonPlug.conn import Conn


async def parse_json(conn: Conn):
    if not conn.req_headers.get("content-type") != "application/json":
        conn.private["json"] = json.loads(await conn.body())
    return conn
