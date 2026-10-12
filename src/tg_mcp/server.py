"""Entry point: `tg-mcp stdio` for local clients, `tg-mcp http` for the remote connector."""

import argparse
import contextlib
import logging

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from tg_mcp.config import Settings
from tg_mcp.telegram import Telegram
from tg_mcp.tools import INSTRUCTIONS, register

log = logging.getLogger("tg_mcp")


def build(settings: Settings) -> tuple[MCPServer, Telegram]:
    mcp = MCPServer(name="telegram", title="Telegram", instructions=INSTRUCTIONS, version="0.1.0")
    tg = Telegram(settings)
    register(mcp, tg, read_only=settings.read_only)
    return mcp, tg


def http_app(settings: Settings) -> Starlette:
    mcp, tg = build(settings)
    allowed_hosts = ["localhost:*", "127.0.0.1:*"]
    if settings.public_host:
        allowed_hosts.append(settings.public_host)
    security = TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=["https://claude.ai", "https://claude.com", "http://localhost:*", "http://127.0.0.1:*"],
    )
    mcp_app = mcp.streamable_http_app(
        streamable_http_path=f"/mcp/{settings.path_secret}",
        stateless_http=True,
        transport_security=security,
    )

    async def healthz(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette):
        async with mcp_app.router.lifespan_context(mcp_app):
            try:
                await tg.client()  # fail fast in logs if the session is dead
                log.info("Telegram connected")
            except Exception:
                log.exception("Telegram connection failed; tools will retry on demand")
            yield
            await tg.close()

    return Starlette(routes=[Route("/healthz", healthz), Mount("/", app=mcp_app)], lifespan=lifespan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="transport", required=True)
    sub.add_parser("stdio")
    http = sub.add_parser("http")
    http.add_argument("--host", default="127.0.0.1")
    http.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("telethon").setLevel(logging.WARNING)

    if args.transport == "stdio":
        mcp, _ = build(Settings.load(need_path_secret=False))
        mcp.run("stdio")
        return

    settings = Settings.load(need_path_secret=True)
    log.info("MCP endpoint: http://%s:%d/mcp/<MCP_PATH_SECRET>", args.host, args.port)
    # access_log off: the request path contains the secret.
    uvicorn.run(http_app(settings), host=args.host, port=args.port, access_log=False, proxy_headers=True)
