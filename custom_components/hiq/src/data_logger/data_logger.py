import asyncio
from datetime import datetime
from datetime import timedelta
from timeit import default_timer

from ..general.misc import create_task_callback
from ..services.rw_service.scgi_communication.rw_request import RWRequest
from .calculate_wait_time import calculate_wait_time
from .data_logger_alarm_handler_service import DataLoggerAlarmHandlerService
from .data_logger_config_util import _extract_tasks
from .data_logger_measurement import DataLoggerMeasurement
from .data_logger_measurement_handler_service import (
    DataLoggerMeasurementHandlerService,
)


class DataLogger:
    def __init__(
        self,
        log,
        loop,
        rw_service,
        repository,
        cache,
        data_logger_activity_service,
        cpu_intensive_task_runner,
    ):
        self._log = log
        self._loop = loop
        self._rw_service = rw_service
        self._measurement_handler_service = DataLoggerMeasurementHandlerService(
            self._log, repository, cpu_intensive_task_runner
        )
        self._alarm_handler_service = DataLoggerAlarmHandlerService(
            self._log, repository
        )
        self._cache = cache
        self._data_logger_activity_service = data_logger_activity_service
        self._cpu_intensive_task_runner = cpu_intensive_task_runner

        self._running_tasks_by_id = {}

    def on_data_logger_config(self, data_logger_config):
        measurement_tasks, alarm_tasks = _extract_tasks(data_logger_config)

        self._data_logger_activity_service.report_tasks_loaded(
            measurement_tasks, alarm_tasks
        )

        self._clear_existing_tasks()
        for task in measurement_tasks:
            self._run_measurement_task(task)
        for task in alarm_tasks:
            self._run_alarm_task(task)

        self._cache.clear()

    def _clear_existing_tasks(self):
        for task in self._running_tasks_by_id.values():
            task.cancel()
        self._running_tasks_by_id.clear()

    async def _handle_measurement(self, task):
        wait_time = calculate_wait_time(task.period, datetime.now())
        self._log.debug(
            lambda: f"Measurement {task.id} scheduled - execution in {wait_time}"
        )
        await asyncio.sleep(wait_time.seconds)

        self._data_logger_activity_service.report_task_triggered(task.id)

        task_start = default_timer()
        self._log.debug(lambda: f"Executing measurement {task.id}")

        valid_measurements, invalid_results_count = await self._read(
            task.targets, task.id
        )

        if invalid_results_count > 0:
            self._log.error(lambda: f"Can't execute measurement {task.id}")
        else:
            await self._measurement_handler_service.on_new_data(valid_measurements)

        task_timedelta = timedelta(seconds=default_timer() - task_start)
        self._log.debug(lambda: f"Measurement {task.id} done in {task_timedelta}")

        self._data_logger_activity_service.report_task_results(
            task.id, len(valid_measurements), invalid_results_count, task_timedelta
        )

        if task.id in self._running_tasks_by_id:
            self._run_measurement_task(task)

    async def _handle_alarm(self, task) -> None:
        wait_time = calculate_wait_time(task.period, datetime.now())
        self._log.debug(lambda: f"Alarm {task.id} scheduled - execution in {wait_time}")
        await asyncio.sleep(wait_time.seconds)

        self._data_logger_activity_service.report_task_triggered(task.id)

        task_start = default_timer()
        self._log.debug(lambda: f"Executing alarm {task.id}")

        valid_measurements, invalid_results_count = await self._read(
            task.targets, task.id
        )

        if invalid_results_count > 0:
            self._log.error(lambda: f"Can't execute alarm {task.id}")
        else:
            await self._alarm_handler_service.on_new_data(
                valid_measurements,
                task.message,
                task.alarm_class,
                task.priority,
                task.range,
                task.type,
            )

        task_timedelta = timedelta(seconds=default_timer() - task_start)
        self._log.debug(lambda: f"Alarm {task.id} done in {task_timedelta}")

        self._data_logger_activity_service.report_task_results(
            task.id, len(valid_measurements), invalid_results_count, task_timedelta
        )

        if task.id in self._running_tasks_by_id:
            self._run_alarm_task(task)

    async def _read(self, targets, task_id):
        preparing_read_start_s = default_timer()
        self._log.debug(lambda: f"Preparing requests for {len(targets)} targets")

        requests = await self._cpu_intensive_task_runner.run(
            self._prepare_requests_blocking, targets
        )

        preparing_read_timedelta = timedelta(
            seconds=default_timer() - preparing_read_start_s
        )
        self._log.debug(lambda: f"Requests prepared in {preparing_read_timedelta}")

        self._log.debug("Reading...")

        responses = await self._rw_service.on_rw_requests(requests, [], task_id)

        valid_measurements = []
        invalid_measurements_count = 0

        for request, response in zip(requests, responses):
            if response.valid:
                valid_measurements.append(
                    DataLoggerMeasurement(
                        request.nad, response.tag_name, response.value
                    )
                )
            else:
                invalid_measurements_count += 1
                self._log.error(lambda: f"Received invalid response: {response}")

        return valid_measurements, invalid_measurements_count

    def _run_measurement_task(self, task):
        self._run_task(task, self._handle_measurement)

    def _run_alarm_task(self, task):
        self._run_task(task, self._handle_alarm)

    def _run_task(self, task, handler):
        t = self._loop.create_task(handler(task))
        t.add_done_callback(create_task_callback(self._log))
        self._running_tasks_by_id[task.id] = t

    @staticmethod
    def _prepare_requests_blocking(targets):
        return [RWRequest.create(f"c{nad}.{variable}") for nad, variable in targets]
