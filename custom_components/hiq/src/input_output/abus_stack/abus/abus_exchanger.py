import asyncio
import logging

from ....general.errors import ExchangerTimeoutError


class AbusExchanger:
    """Handles request-response cycles."""

    def __init__(self, loop, sender, timeout, retry):
        self._communication_loop = loop
        self._sender = sender
        self._pending = {}

        # sequence of (request, future) tuples where future will be resolved with future
        # response or error
        self._requests_queue = asyncio.Queue(loop=self._communication_loop)

        # holds exchange tag of the most recently sent request. It has to be remembered throughout
        # the read cycle so it can be compared with responses' exchange tags
        self._last_exchange_tag = None

        # pending response for the request which has just been pulled from queue and sent
        self._current_pending_response = None

        self._timeout = timeout
        self._retry = retry

        self._communication_loop.create_task(self._handle_requests_queue())

    async def _handle_requests_queue(self):
        try:
            while True:
                (request, future) = await self._requests_queue.get()

                try:
                    response = await self._exchange_with_retry_and_timeout(request)
                    future.set_result(response)
                except ExchangerTimeoutError as e:
                    future.set_exception(e)
        except Exception as e:
            logging.getLogger().error("Error in abus exchanger")
            logging.getLogger().error(e)

    async def exchange_threadsafe(self, request):
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(
                self._exchange_on_communication_loop(request), self._communication_loop
            )
        )

    async def _exchange_on_communication_loop(self, request):
        future_response = self._communication_loop.create_future()

        self._requests_queue.put_nowait((request, future_response))

        return await future_response

    async def _exchange_with_retry_and_timeout(self, request):
        retry = self._retry

        while retry > 0:
            try:
                return await self._exchange(request)
            except asyncio.TimeoutError:
                retry -= 1
        raise ExchangerTimeoutError()

    async def _exchange(self, request):
        if self._current_pending_response is not None:
            raise Exception("Current pending response should not exist")

        self._current_pending_response = self._communication_loop.create_future()
        self._last_exchange_tag = self._extract_exchange_tag_from_request(request)

        self._sender.send(request)

        try:
            return await asyncio.wait_for(
                self._current_pending_response, self._timeout.total_seconds()
            )
        finally:
            self._current_pending_response = None
            self._last_exchange_tag = None

    def receive(self, abus_msg):
        exchange_tags_match = (
            self._extract_exchange_tag_from_response(abus_msg)
            == self._last_exchange_tag
        )

        if (
            exchange_tags_match
            and self._current_pending_response is not None
            and not self._current_pending_response.done()
        ):
            self._current_pending_response.set_result(abus_msg)

            self._last_exchange_tag = None
            self._current_pending_response = None

    @staticmethod
    def _extract_exchange_tag_from_request(abus_request):
        return abus_request.from_nad, abus_request.to_nad, abus_request.transaction_id

    @staticmethod
    def _extract_exchange_tag_from_response(abus_response):
        return (
            abus_response.to_nad,
            abus_response.from_nad,
            abus_response.transaction_id,
        )
