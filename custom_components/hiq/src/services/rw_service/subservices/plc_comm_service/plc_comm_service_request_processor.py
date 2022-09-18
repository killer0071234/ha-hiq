from abc import ABC
from abc import abstractmethod

from .....services.rw_service.subservices.plc_comm_service.plc_rw_request import AlcData
from .....services.rw_service.subservices.plc_comm_service.plc_rw_request import (
    PlcRWRequest,
)
from .....services.rw_service.subservices.plc_comm_service.plc_rw_requests import (
    PlcRWRequests,
)


class PlcCommServiceRequestProcessor(ABC):
    def __init__(self, log, client, cpu_intensive_task_runner):
        self._log = log
        self._client = client
        self._cpu_intensive_task_runner = cpu_intensive_task_runner

    @property
    def _nad(self):
        return self._client.plc_info.nad

    async def process(self, requests, alc):
        plc_rw_requests = self._create_plc_rw_requests(requests, alc)
        return await self._process_plc_rw_requests(plc_rw_requests)

    @abstractmethod
    async def _process_plc_rw_requests(self, requests):
        pass

    @classmethod
    def _create_plc_rw_requests(cls, requests, alc):
        result = PlcRWRequests()

        for request in requests:
            plc_request = cls._create_plc_rw_request(request, alc)
            result.add(plc_request)

        return result

    @classmethod
    def _create_plc_rw_request(cls, request, alc):
        var_name = request.tag_name

        try:
            var_info = alc[var_name]
            alc_data = AlcData(
                var_info.address,
                var_info.size,
                var_info.data_type,
                var_info.description,
            )
            return PlcRWRequest.create(
                request.name,
                request.value,
                var_name,
                alc_data=alc_data,
                idx=request.idx,
            )
        except KeyError:
            return PlcRWRequest.create(
                request.name, request.value, var_name, idx=request.idx
            )
