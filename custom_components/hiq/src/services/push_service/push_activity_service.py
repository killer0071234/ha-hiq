class PushActivityService:
    def __init__(self):
        self._push_requests_received_count = 0
        self._successful_push_acknowledgments_count = 0
        self._failed_push_acknowledgments_count = 0

    @property
    def push_requests_received_count(self):
        return self._push_requests_received_count

    @property
    def successful_push_acknowledgments_count(self):
        return self._successful_push_acknowledgments_count

    @property
    def failed_push_acknowledgments_count(self):
        return self._failed_push_acknowledgments_count

    def report_push_request_received(self):
        self._push_requests_received_count += 1

    def report_push_acknowledgment_succeeded(self):
        self._successful_push_acknowledgments_count += 1

    def report_push_acknowledgment_failed(self):
        self._failed_push_acknowledgments_count += 1
