from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Optional


@dataclass
class TaskActivity:
    trigger_count: int = 0
    last_trigger_datetime: Optional[datetime] = None
    valid_results: int = 0
    invalid_results: int = 0
    duration: Optional[timedelta] = None

    def report_task_triggered(self):
        self.trigger_count += 1
        self.last_trigger_datetime = datetime.now()

    def report_task_results(self, valid_count, invalid_count, duration):
        self.valid_results = valid_count
        self.invalid_results = invalid_count
        self.duration = duration


class DataLoggerActivityService:
    def __init__(self):
        self._measurement_tasks = []
        self._alarm_tasks = []
        self._task_activities = {}

    def __getitem__(self, task_id):
        try:
            return self._task_activities[task_id]
        except KeyError:
            task_activity = TaskActivity()
            self._task_activities[task_id] = task_activity
            return task_activity

    def report_tasks_loaded(self, measurement_tasks, alarm_tasks):
        self._measurement_tasks = measurement_tasks
        self._alarm_tasks = alarm_tasks
        self._task_activities = {}

    def report_task_triggered(self, task_id):
        self[task_id].report_task_triggered()

    def report_task_results(self, task_id, valid_count, invalid_count, duration):
        self[task_id].report_task_results(valid_count, invalid_count, duration)

    @property
    def measurement_tasks(self):
        return self._measurement_tasks

    @property
    def alarm_tasks(self):
        return self._alarm_tasks
