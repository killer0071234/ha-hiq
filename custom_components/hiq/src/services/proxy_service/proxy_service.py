import asyncio

from ...input_output.abus_stack.abus.abus_message import AbusMessage
from ...input_output.abus_stack.abus.command_frame import CommandFrameUtil
from ...services.plc_info_service.plc_info import PlcInfo


class ProxyService:
    def __init__(
        self,
        log,
        plc_info_service,
        plc_client_manager,
        main_loop,
        communication_loop,
        proxy_activity_service,
        repository,
        db_synchronizer,
    ):
        self._log = log
        self._router = None
        self._plc_info_service = plc_info_service
        self._plc_client_manager = plc_client_manager
        self._main_loop = main_loop
        self._communication_loop = communication_loop
        self._proxy_activity_service = proxy_activity_service
        self._repository = repository
        self._db_synchronizer = db_synchronizer

    def start(self):
        self._db_synchronizer.start()

    def set_router(self, router):
        self._router = router

    def _get_proxy_plc_info_for_nad(self, nad):
        try:
            plc_info = self._plc_info_service.get_plc_info(nad)
            if plc_info.origin == PlcInfo.Origin.PROXY:
                return plc_info
        except KeyError:
            pass

    def receive(self, abus_msg):
        """communication loop"""

        self._log.debug(f"Received on communication loop: {abus_msg}")

        # handle abus_msg asynchronously (without blocking) by scheduling task on communication loop

        asyncio.run_coroutine_threadsafe(self._receive_async(abus_msg), self._main_loop)

    async def _receive_async(self, received_abus_msg):
        """main_loop"""

        self._log.debug(f"Received on main loop: {received_abus_msg}")

        abus_msgs = await self._handle_proxy_msg(received_abus_msg)

        abus_msg_strings = ", ".join(f"{abus_msg}" for abus_msg in abus_msgs)
        self._log.debug(f"Sending: {abus_msg_strings}")

        asyncio.run_coroutine_threadsafe(
            self._send_async(abus_msgs), self._communication_loop
        )

    async def _send_async(self, abus_msgs):
        for abus_msg in abus_msgs:
            self._router.send(abus_msg)

    async def _handle_proxy_msg(self, abus_msg):
        """main loop"""

        from_nad = abus_msg.from_nad
        session_plc_info = self._get_proxy_plc_info_for_nad(from_nad)

        if session_plc_info is not None:
            # to plc
            self._proxy_activity_service.report_to_plc(from_nad, abus_msg.to_nad)
            return await self._create_proxy_msgs_to_plc(abus_msg)
        else:
            if await self._repository.exist_in_relays_table(from_nad):
                self._proxy_activity_service.report_to_plc(from_nad, abus_msg.to_nad)
                # to plc
                self._plc_info_service.update(
                    from_nad, abus_msg.ip, abus_msg.port, PlcInfo.Origin.PROXY
                )
                return await self._create_proxy_msgs_to_plc(abus_msg)
            else:
                # from plc
                to_nad = abus_msg.to_nad
                session_plc_info = self._get_proxy_plc_info_for_nad(to_nad)
                if session_plc_info is not None:
                    abus_msg.addr = session_plc_info.ip, session_plc_info.port
                    self._proxy_activity_service.report_from_plc(
                        to_nad, abus_msg.from_nad
                    )
                    return (abus_msg,)
                else:
                    return []

    async def _create_proxy_msgs_to_plc(self, abus_msg):
        if abus_msg.to_nad == 0:
            return [
                ProxyService.create_autodetect_acknowledge_abus_msg(plc_info, abus_msg)
                for plc_info in self._plc_info_service.get_non_proxy_plc_infos()
            ]

        plc_client = await self._plc_client_manager.get(abus_msg.to_nad)
        if plc_client is not None:
            plc_info = plc_client.plc_info
            abus_msg.addr = plc_info.ip, plc_info.port
            return [abus_msg]
        else:
            return []

    @staticmethod
    def create_autodetect_acknowledge_abus_msg(plc_info, detection_request):
        """When client wants to detect plcs his requests are addressed to nad 0. Scgi server doesn't
        forward these messages to actual plcs, instead it just uses information in plc info list
        and creates responses as if they came from plcs"""

        return AbusMessage(
            (detection_request.ip, detection_request.port),
            plc_info.nad,
            detection_request.from_nad,
            detection_request.transaction_id,
            CommandFrameUtil.create_autodetect_response(),
        )
