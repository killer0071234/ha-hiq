from datetime import datetime
from datetime import timedelta

from ...constants import PLC_INFO_CLEAR_PERIOD
from ...constants import PLC_INFO_LIFETIME
from ...general.timed_executor import Timer


class PlcInfoCleaner(Timer):
    def __init__(self, log, plc_info_service, config):
        super().__init__(timedelta(minutes=PLC_INFO_CLEAR_PERIOD).total_seconds())
        self._log = (log,)
        self._plc_info_service = plc_info_service
        self._plc_info_lifetime = timedelta(minutes=PLC_INFO_LIFETIME)

    async def execute(self):

        nads_to_remove = [
            plc_info.nad
            for plc_info in self._plc_info_service.get_plc_infos()
            if self._should_remove_plc_info(plc_info)
        ]

        for nad in nads_to_remove:
            await self._plc_info_service.remove_plc_info(nad)

    def _should_remove_plc_info(self, plc_info):
        if (
            plc_info.origin == plc_info.Origin.PROXY
            or plc_info.origin == plc_info.Origin.STATIC
        ):
            return False

        plc_info_age = datetime.now() - plc_info.last_update_time

        return plc_info_age > self._plc_info_lifetime
