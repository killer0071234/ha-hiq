from ...services.rw_service.errors import RWServiceError
from ...services.rw_service.errors import ScgiCommunicationError
from ...services.rw_service.scgi_communication.rw_request import RWRequest
from .errors import ScgiError
from .operation import OperationUtil
from .rw_responses_xml_serializer import RWResponsesXmlSerializer


class ScgiServer:
    def __init__(self, log, rw_service, scgi_activity_service, config):
        self._log = log
        self._rw_service = rw_service
        self._scgi_activity_service = scgi_activity_service
        self._reply_with_descriptions = config.scgi_config.reply_with_descriptions

    async def on_data(self, data):
        self._scgi_activity_service.report_request_received()

        response_str = await self._on_data(data)
        response = response_str.encode()

        self._scgi_activity_service.report_response_sent()

        return response

    async def _on_data(self, data):
        try:
            r_operations, w_operations = OperationUtil.bytes_to_operations(data)

            r_requests = [
                RWRequest.create(operation.key, operation.value)
                for operation in r_operations
            ]

            w_requests = [
                RWRequest.create(operation.key, operation.value)
                for operation in w_operations
            ]

            responses = await self._rw_service.on_rw_requests(r_requests, w_requests)

            xml = RWResponsesXmlSerializer.to_xml(
                responses, self._reply_with_descriptions
            )

            return f"HTTP/1.1 200 OK\r\n\r\n{xml}"
        except (ScgiError, ScgiCommunicationError) as e:
            self._log.error("Bad request", exc_info=e)
            return "HTTP/1.1 400 Bad Request"
        except RWServiceError as e:
            self._log.error("Internal Server Error", exc_info=e)
            return "HTTP/1.1 500 Internal Server Error"
