from datetime import datetime

from ..input_output.db.model import Measurement


class DataLoggerMeasurementHandlerService:
    def __init__(self, log, repository, cpu_intensive_task_runner):
        self._log = log
        self._repository = repository
        self._cpu_intensive_task_runner = cpu_intensive_task_runner

    async def on_new_data(self, measurements) -> None:
        self._log.debug(lambda: f"Measurement - {len(measurements)} variables")

        data = await self._cpu_intensive_task_runner.run(
            self._map_measurements_to_domain_objects, measurements
        )

        await self._repository.create_measurements(data)

    @staticmethod
    def _map_measurements_to_domain_objects(measurements):
        return [
            Measurement(None, m.nad, m.variable, m.value, datetime.now())
            for m in measurements
        ]
