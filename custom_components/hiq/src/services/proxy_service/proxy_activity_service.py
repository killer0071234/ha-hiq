from datetime import datetime


class ProxyActivityService:
    def __init__(self, plc_info_service, repository):
        self.plc_proxy_activities_by_session_id = {}
        self._plc_info_service = plc_info_service
        self._repository = repository

    def extract_proxy_activities(self):
        return self.plc_proxy_activities_by_session_id.items()

    def _delete_plc_proxy_activity(self, session_id):
        try:
            del self.plc_proxy_activities_by_session_id[session_id]
        except KeyError:
            pass

    def report_to_plc(self, session_id, nad):
        plc_proxy_activity = self.plc_proxy_activities_by_session_id.get(
            session_id, None
        )

        if plc_proxy_activity is None:
            plc_proxy_activity = PlcProxyActivity(datetime.now(), nad)
            self.plc_proxy_activities_by_session_id[session_id] = plc_proxy_activity

        plc_proxy_activity.increment_rx()
        plc_proxy_activity.update_last_msg_datetime()
        plc_proxy_activity.update_last_plc_nad(nad)

    def report_from_plc(self, session_id, nad):
        plc_proxy_activity = self.plc_proxy_activities_by_session_id.get(
            session_id, None
        )

        if plc_proxy_activity is None:
            plc_proxy_activity = PlcProxyActivity(datetime.now(), nad)
            self.plc_proxy_activities_by_session_id[session_id] = plc_proxy_activity

        plc_proxy_activity.increment_tx()
        plc_proxy_activity.update_last_msg_datetime()
        plc_proxy_activity.update_last_plc_nad(nad)

    async def update_from_db(self):
        proxy_plc_infos_session_ids = []
        for plc_info in self._plc_info_service.get_proxy_plc_infos():
            session_id = plc_info.nad

            proxy_plc_infos_session_ids.append(session_id)

            plc_proxy_activity = self.plc_proxy_activities_by_session_id.get(
                session_id, None
            )
            if plc_proxy_activity is None:
                continue

            await self._repository.update_relays(session_id, plc_proxy_activity)

        session_ids_from_db = await self._repository.get_enabled_with_session_id_in(
            proxy_plc_infos_session_ids
        )

        proxy_plc_infos = list(self._plc_info_service.get_proxy_plc_infos())

        for plc_info in proxy_plc_infos:
            session_id = plc_info.nad
            if session_id not in session_ids_from_db:
                self._plc_info_service.remove_plc_info(session_id)
                self._delete_plc_proxy_activity(session_id)


class PlcProxyActivity:
    def __init__(self, last_msg, last_plc_nad, msg_count_rx=0, msg_count_tx=0):
        self.last_msg = last_msg
        self.last_plc_nad = last_plc_nad
        self.msg_count_rx = msg_count_rx
        self.msg_count_tx = msg_count_tx

    def increment_rx(self):
        self.msg_count_rx += 1

    def increment_tx(self):
        self.msg_count_tx += 1

    def update_last_msg_datetime(self):
        self.last_msg = datetime.now()

    def update_last_plc_nad(self, nad):
        self.last_plc_nad = nad
