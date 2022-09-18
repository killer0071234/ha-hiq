from dataclasses import dataclass
from typing import Dict
from typing import Set

from ......services.rw_service.scgi_communication.r_response import RResponse
from ......services.rw_service.scgi_communication.rw_request import RWRequest
from ......services.rw_service.subservices.plc_comm_service.plc_cache.cache_value_condition import (
    CacheValueCondition,
)


@dataclass(frozen=True)
class ReadResult:
    fresh: Dict[RWRequest, RResponse]
    stinky: Dict[RWRequest, RResponse]
    not_available: Set[RWRequest]


class PlcCacheFacade:
    """
    Nicer interface for `SinglePlcCache`
    """

    def __init__(self, log, cache):
        self._log = log
        self._cache = cache

    def start_futures(self, requests):
        for request in requests:
            self._cache.start_future(request.tag_name)

    def write(self, responses):
        for response in responses:
            name = response.tag_name
            if response.valid:
                self._cache.set_value(name, response.value, response.description)
            else:
                self._cache.cancel_future(name)

    async def read(self, requests):
        fresh = {}
        stinky = {}
        not_available_immediately = set()

        for request in requests:
            name = request.tag_name
            try:
                value = self._cache.get_value(name)
                if value.condition == CacheValueCondition.FRESH:
                    fresh[request] = self._create_r_response_from_cached_value(
                        request, value
                    )
                elif value.condition == CacheValueCondition.STINKY:
                    stinky[request] = self._create_r_response_from_cached_value(
                        request, value
                    )
                else:
                    not_available_immediately.add(request)
            except KeyError:
                not_available_immediately.add(request)

        not_available = set()

        for request in not_available_immediately:
            name = request.tag_name
            try:
                value = await self._cache.get_future_value(name)
                fresh[request] = self._create_r_response_from_cached_value(
                    request, value
                )
            except KeyError:
                not_available.add(request)

        return ReadResult(fresh, stinky, not_available)

    @classmethod
    def _create_r_response_from_cached_value(cls, request, cache_value):
        return RResponse.create(
            request.name,
            request.tag_name,
            cache_value.value,
            cache_value.description,
            cached=True,
        )
