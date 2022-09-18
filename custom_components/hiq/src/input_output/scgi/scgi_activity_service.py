from datetime import datetime


class ScgiActivityService:
    def __init__(self):
        self._server_start_datetime = datetime.now()
        self._requests_received_count = 0
        self._responses_sent_count = 0

    @property
    def requests_received_count(self):
        return self._requests_received_count

    @property
    def responses_sent_count(self):
        return self._responses_sent_count

    @property
    def pending_requests_count(self):
        return self._requests_received_count - self._responses_sent_count

    @property
    def server_uptime(self):
        return datetime.now() - self._server_start_datetime

    def report_request_received(self):
        self._requests_received_count += 1

    def report_response_sent(self):
        self._responses_sent_count += 1
