from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from enum import auto
from enum import Enum
from typing import Optional

from .....services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.plc_head import (
    PlcHead,
)
from .....services.rw_service.subservices.plc_comm_service.plc_client_manager.plc_client.status import (
    PlcStatus,
)


@dataclass
class PlcActivity:
    class DeviceStatus(Enum):
        UNKNOWN = (auto(),)
        OFFLINE = (auto(),)
        NO_PROGRAM = (auto(),)
        OK = auto()

    last_successful_exchange_time: Optional[datetime] = None
    last_failed_exchange_time: Optional[datetime] = None
    initiated_exchanges_count: int = 0
    successful_exchanges_count: int = 0
    failed_exchanges_count: int = 0
    bytes_transferred: int = 0
    last_used_alc_crc: Optional[int] = None
    last_plc_head: Optional[PlcHead] = None
    last_plc_status: Optional[PlcStatus] = None
    last_exchange_duration: Optional[timedelta] = None

    @property
    def finished_exchanges_count(self) -> int:
        return self.successful_exchanges_count + self.failed_exchanges_count

    def pending_exchanges_count(self) -> int:
        return self.initiated_exchanges_count - self.finished_exchanges_count

    @property
    def device_status(self) -> DeviceStatus:
        if self.successful_exchanges_count == 0:
            if self.failed_exchanges_count == 0:
                return self.DeviceStatus.UNKNOWN
            else:
                return self.DeviceStatus.OFFLINE
        else:
            if self.failed_exchanges_count == 0:
                return self._device_status_from_plc_head
            else:
                is_error_recent = (
                    self.last_successful_exchange_time < self.last_failed_exchange_time
                )
                if is_error_recent:
                    return self.device_status.OFFLINE
                else:
                    return self._device_status_from_plc_head

    @property
    def _device_status_from_plc_head(self) -> DeviceStatus:
        plc_head = self.last_plc_head
        if plc_head is None:
            return self.DeviceStatus.UNKNOWN

        if plc_head.empty == 0:
            return self.DeviceStatus.OK
        return self.DeviceStatus.NO_PROGRAM
