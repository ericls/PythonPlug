import functools
from collections import OrderedDict, namedtuple
from http import HTTPStatus
from types import FunctionType
from typing import Callable, Iterable, Optional

from werkzeug.routing import Map, MethodNotAllowed, NotFound, RequestRedirect, Rule

from PythonPlug import Conn
from PythonPlug.plug import Plug

Forward = namedtuple("Forward", ["to", "change_path"])


class RouterPlug(Plug):
    def __init__(self):
        super().__init__()
        self.url_map = Map()
        self.endpoint_to_plug = {}
        self.forwards = OrderedDict()

    def route(self, rule, methods=None, name=""):
        methods = set(methods) if methods is not None else None
        if methods and not "OPTIONS" in methods:
            methods.add("OPTIONS")

        def decorator(name: Optional[str], plug: Callable):
            self.add_route(rule_string=rule, plug=plug, methods=methods, name=name)
            return plug

        return functools.partial(decorator, name)

    async def call(self, conn: Conn):
        try:
            rule, args = self.url_adapter(conn).match(
                return_rule=True, method=conn.scope.get("method")
            )
        except RequestRedirect as e:
            return await conn.redirect(e.new_url, code=302)
        except MethodNotAllowed as e:
            return await conn.send_resp(b"", HTTPStatus.METHOD_NOT_ALLOWED, halt=True)
        except NotFound as e:

            def prefix_matcher(prefix):
                return conn.private["remaining_path"].startswith(prefix)

            forward_matches = sorted(filter(prefix_matcher, self.forwards), key=len)
            if forward_matches:
                match = forward_matches[0]
                router, change_path = self.forwards[match]
                conn.private.setdefault("consumed_path", []).append(match)
                conn.private["remaining_path"] = conn.private["remaining_path"][
                    len(match) :
                ]
                if change_path:
                    conn._scope["path"] = conn.private["remaining_path"]
                return await router(conn)
            return conn
        else:
            plug = self.endpoint_to_plug.get(rule.endpoint)
            conn.private.setdefault("router_args", {}).update(args)
            return await plug(conn)

    def url_adapter(self, conn: Conn):
        scope = conn.scope
        remaining_path = conn.private.get("remaining_path")
        if remaining_path is None:
            remaining_path = conn.private["remaining_path"] = scope.get("path")
        return self.url_map.bind(
            conn.req_headers.get("host"),
            path_info=remaining_path,
            script_name=scope.get("root_path", "") or None,
            url_scheme=scope.get("scheme"),
            query_args=scope.get("query_string", b""),
        )

    def add_route(
        self,
        *,
        rule_string: str,
        plug: Callable,
        name: Optional[str] = None,
        methods: Optional[Iterable[str]] = None,
    ):
        if not name:
            if isinstance(plug, FunctionType):
                name = plug.__name__
            if isinstance(plug, Plug):
                name = type(plug).__name__
        assert name not in self.endpoint_to_plug, (
            "a plug is overwriting an existing plug: %s" % name
        )
        self.url_map.add(Rule(rule_string, endpoint=name, methods=methods))
        self.endpoint_to_plug[name] = plug

    def forward(self, prefix, router=None, change_path=False):
        assert prefix not in self.forwards, (
            "Cannot forward same prefix to different routers: %s" % prefix
        )
        self.forwards[prefix] = Forward(router, change_path)
        return router
