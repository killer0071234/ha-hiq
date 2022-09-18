from ....services.plc_info_service.errors import PlcInfoNotFoundError


class SinglePlcStatusService:
    """
    Exposes status for specific plc
    """

    def __init__(self, nad, plc_info_service, plc_activity_service, alc_service):
        self._nad = nad
        self._plc_info_service = plc_info_service
        self._plc_activity_service = plc_activity_service
        self._alc_service = alc_service

    @property
    def timestamp(self):
        try:
            return self.plc_info.program_datetime
        except PlcInfoNotFoundError:
            return None

    @property
    def ip_port(self):
        try:
            plc_info = self.plc_info
            return plc_info.ip, plc_info.port
        except PlcInfoNotFoundError:
            return None

    @property
    def response_time(self):
        return self.plc_activity.last_exchange_duration

    @property
    def has_alc(self):
        return self.plc_activity.last_used_alc_crc is not None

    @property
    def device_status(self):
        return self.plc_activity.device_status

    @property
    def plc_status(self):
        return self.plc_activity.last_plc_status

    @property
    def bytes_transferred(self):
        return self.plc_activity.bytes_transferred

    async def get_alc_text(self):
        crc = self.plc_activity.last_used_alc_crc
        if crc is not None:
            return await self._alc_service.load_alc_text_for_crc(crc)

    @property
    def communication_error_count(self):
        return self.plc_activity.failed_exchanges_count

    @property
    def plc_info(self):
        return self._plc_info_service.get_plc_info(self._nad)

    @property
    def plc_activity(self):
        return self._plc_activity_service[self._nad]
