from datetime import datetime

from .....services.rw_service.subservices.plc_activity_service.plc_activity import (
    PlcActivity,
)


class PlcActivityService:
    """
    Manages activity information for every plc
    """

    def __init__(self):
        self._activities = {}

    def __getitem__(self, nad):
        try:
            return self._activities[nad]
        except KeyError:
            activity = PlcActivity()
            self._activities[nad] = activity
            return activity

    def report_exchange_initiated(self, nad):
        activity = self[nad]
        activity.initiated_exchanges_count += 1

    def report_exchange_succeeded(self, nad, bytes_count, duration):
        activity = self[nad]
        activity.last_successful_exchange_time = datetime.now()
        activity.successful_exchanges_count += 1
        activity.bytes_transferred += bytes_count
        activity.last_exchange_duration = duration

    def report_exchange_failed(self, nad: int):
        activity = self[nad]
        activity.last_failed_exchange_time = datetime.now()
        activity.failed_exchanges_count += 1
        activity.last_exchange_duration = None

    def report_alc_crc_used(self, nad: int, alc_crc):
        self[nad].last_used_alc_crc = alc_crc

    def report_plc_head_used(self, nad: int, plc_head):
        self[nad].last_plc_head = plc_head

    def report_plc_status_used(self, nad: int, plc_status):
        self[nad].last_plc_status = plc_status
