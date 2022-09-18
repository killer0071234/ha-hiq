import asyncio
import ssl


class TCPServer:
    PAYLOAD_BYTES = 16 * 1024

    def __init__(self, log, loop, handler, config):
        self._log = log
        self._loop = loop
        self._handler = handler
        self._addr = (
            config.scgi_config.scgi_bind_address,
            config.scgi_config.scgi_port,
        )
        self._ssl = config.scgi_config.tls_enabled

    async def start(self):
        if self._ssl:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain("tls/private.crt", "tls/private.key")

        server = await asyncio.start_server(
            self._handle,
            host=self._addr[0],
            port=self._addr[1],
            start_serving=True,
            ssl=ssl_context if self._ssl else None,
        )
        (host, port, *rest) = server.sockets[0].getsockname()
        self._log.info(lambda: f"Listening on {host}:{port}")

    async def on_request(self, request_bytes):
        response_bytes = await self._handler.on_data(request_bytes)
        return response_bytes

    async def _handle(self, reader, writer):
        request_bytes = await reader.read(self.PAYLOAD_BYTES)
        if request_bytes != b"":
            response_bytes = await self.on_request(request_bytes)
            writer.write(response_bytes)
            await writer.drain()
            writer.close()
