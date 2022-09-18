from ....services.status_services.plc_status_service.single_plc_status_service import (
    SinglePlcStatusService,
)


class PlcStatusService:
    """
    Exposes status for all plcs
    """

    def __init__(self, plc_info_service, plc_activity_service, alc_service):
        self._plc_info_service = plc_info_service
        self._plc_activity_service = plc_activity_service
        self._plc_status_services = {}
        self._alc_service = alc_service

    def __getitem__(self, nad):
        try:
            return self._plc_status_services[nad]
        except KeyError:
            result = SinglePlcStatusService(
                nad,
                self._plc_info_service,
                self._plc_activity_service,
                self._alc_service,
            )
            self._plc_status_services[nad] = result
            return result
