from datetime import datetime

from ...constants import ABUS_BROADCAST_PORT
from ...services.plc_info_service.plc_info import PlcInfo


class PlcInfoService:
    def __init__(self, log, loop, config):
        self._log = log
        self._loop = loop
        self._abus_config = config.abus_config
        self._scgi_config = config.scgi_config
        self._lifetime = config.push_config.timeout_h
        self._static_plcs_config = config.static_plcs_config
        self._plc_infos_by_nad = {}
        self._plc_client_manager = None

    def load_static_plc_infos(self):
        self._load_static_plc_infos(self._static_plcs_config.static_plcs_configs)

    def set_plc_client_manager(self, plc_client_manager):
        self._plc_client_manager = plc_client_manager

    def get_non_proxy_plc_infos(self):
        return (
            plc_info
            for plc_info in self.get_plc_infos()
            if plc_info.origin != PlcInfo.Origin.PROXY
        )

    def get_proxy_plc_infos(self):
        return (
            plc_info
            for plc_info in self.get_plc_infos()
            if plc_info.origin == PlcInfo.Origin.PROXY
        )

    def get_plc_infos(self):
        return self._plc_infos_by_nad.values()

    def get_push_plc_infos(self):
        return (
            plc_info
            for plc_info in self.get_plc_infos()
            if plc_info.origin == PlcInfo.Origin.PUSH
        )

    def get_static_plc_infos(self):
        return (
            plc_info
            for plc_info in self.get_plc_infos()
            if plc_info.origin == PlcInfo.Origin.STATIC
        )

    def get_auto_plc_infos(self):
        return (
            plc_info
            for plc_info in self.get_plc_infos()
            if plc_info.origin == PlcInfo.Origin.AUTO
        )

    def update(self, nad, ip, port, origin):
        try:
            old_plc_info = self._plc_infos_by_nad[nad]

            if (
                old_plc_info.ip == ip
                and old_plc_info.port == port
                and old_plc_info.origin == origin
            ):
                return old_plc_info

            new_plc_info = self.create(
                origin, old_plc_info.nad, ip, old_plc_info.port, old_plc_info.password
            )
        except KeyError:
            new_plc_info = self.create(origin, nad, ip, port)

        self.set_plc_info(new_plc_info)
        return new_plc_info

    def update_program_datetime(self, nad, program_datetime):
        old_plc_info = self._plc_infos_by_nad[nad]

        if old_plc_info.program_datetime == program_datetime:
            return old_plc_info

        new_plc_info = self.create(
            old_plc_info.origin,
            old_plc_info.nad,
            old_plc_info.ip,
            old_plc_info.port,
            old_plc_info.password,
            program_datetime,
        )

        self.set_plc_info(new_plc_info)
        return new_plc_info

    def create(
        self,
        origin=None,
        nad=None,
        ip=None,
        port=None,
        password=None,
        program_datetime=None,
        last_update_time=None,
    ):
        if ip == "0.0.0.0":
            port = 0

        if port is None:
            port = ABUS_BROADCAST_PORT

        if last_update_time is None:
            last_update_time = datetime.now()

        return PlcInfo(
            datetime.now(),
            origin,
            nad,
            ip,
            port,
            self._abus_config.password if password is None else password,
            program_datetime,
            last_update_time,
        )

    def get_plc_info(self, nad):
        return self._plc_infos_by_nad[nad]

    def set_plc_info(self, plc_info):
        self._plc_infos_by_nad[plc_info.nad] = plc_info
        self._log.debug(f"Added plc info c{plc_info.nad}: {plc_info}")

        self._plc_client_manager.on_plc_info_set(plc_info)

    async def remove_plc_info(self, nad):
        del self._plc_infos_by_nad[nad]
        self._log.debug(f"Removed plc info c{nad}")

        self._plc_client_manager.on_plc_info_removed(nad)

    def _load_static_plc_infos(self, static_plcs_config):
        plc_infos = self._static_plc_configs_to_plc_infos(static_plcs_config)
        for plc_info in plc_infos:
            self.set_plc_info(plc_info)

    def _static_plc_configs_to_plc_infos(self, static_plcs_config):
        return (
            self._static_plc_config_to_plc_info(static_plc_config)
            for static_plc_config in static_plcs_config
        )

    def _static_plc_config_to_plc_info(self, static_plc_config):
        nad = static_plc_config.nad
        ip = static_plc_config.ip if static_plc_config.ip != "" else None
        port = static_plc_config.port
        password = (
            static_plc_config.password if static_plc_config.password != "" else None
        )
        return self.create(
            PlcInfo.Origin.STATIC,
            nad,
            ip,
            port,
            password,
        )
