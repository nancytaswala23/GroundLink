import sys
sys.path.insert(0, "/app")

from datetime import datetime, timedelta
import pytest

from models.models import TaskPriority, TaskStatus, StationStatus
from scheduler.scheduler import TaskScheduler
from station_manager.station_manager import StationManager


@pytest.fixture
def scheduler():
    return TaskScheduler()


@pytest.fixture
def station_manager():
    sm = StationManager()
    sm.register_station("Alaska", 500.0, "GS-001")
    sm.register_station("Chile", 300.0, "GS-002")
    sm.register_station("Australia", 400.0, "GS-003")
    return sm


def make_task(scheduler, satellite_id="SAT-1", priority=TaskPriority.MEDIUM):
    now = datetime.utcnow()
    return scheduler.submit_task(
        satellite_id=satellite_id,
        window_start=now,
        window_end=now + timedelta(minutes=10),
        data_volume_mb=100.0,
        priority=priority,
    )


class TestTaskSubmission:
    def test_submit_task_added_to_queue(self, scheduler):
        task = make_task(scheduler)
        assert task.task_id in scheduler._task_registry
        assert task.status == TaskStatus.PENDING

    def test_multiple_tasks_queued(self, scheduler):
        for _ in range(5):
            make_task(scheduler)
        assert len(scheduler._queue) == 5


class TestPriorityScheduling:
    def test_high_priority_assigned_first(self, scheduler, station_manager):
        make_task(scheduler, "SAT-1", TaskPriority.LOW)
        make_task(scheduler, "SAT-2", TaskPriority.CRITICAL)
        make_task(scheduler, "SAT-3", TaskPriority.MEDIUM)

        station = station_manager.get_station("GS-001")
        task = scheduler.assign_next_task(station)

        assert task.satellite_id == "SAT-2"  # CRITICAL should go first
        assert task.status == TaskStatus.ASSIGNED

    def test_task_assigned_to_station(self, scheduler, station_manager):
        make_task(scheduler)
        station = station_manager.get_station("GS-001")
        task = scheduler.assign_next_task(station)

        assert task.assigned_station == "GS-001"
        assert station.status == StationStatus.BUSY


class TestFaultTolerance:
    def test_station_failure_triggers_reassignment(self, scheduler, station_manager):
        make_task(scheduler, "SAT-1", TaskPriority.HIGH)
        station1 = station_manager.get_station("GS-001")
        station2 = station_manager.get_station("GS-002")

        scheduler.assign_next_task(station1)
        assert station1.status == StationStatus.BUSY

        all_stations = station_manager.get_all_stations()
        reassigned = scheduler.handle_station_failure(station1, all_stations)

        assert station1.status == StationStatus.FAILED
        assert reassigned is not None
        assert reassigned.assigned_station == "GS-002"
        assert station2.status == StationStatus.BUSY

    def test_failed_task_requeued_when_no_stations(self, scheduler, station_manager):
        make_task(scheduler, "SAT-1", TaskPriority.HIGH)
        stations = station_manager.get_all_stations()

        # Busy all stations
        for sid, station in stations.items():
            station.status = StationStatus.BUSY

        station1 = station_manager.get_station("GS-001")
        station1.current_task = scheduler._queue[0][1].task_id
        station1.status = StationStatus.BUSY

        result = scheduler.handle_station_failure(station1, stations)
        assert result is None  # no available station
        assert len(scheduler._queue) >= 1  # task requeued


class TestConflictResolution:
    def test_higher_priority_wins_conflict(self, scheduler):
        now = datetime.utcnow()
        task_a = scheduler.submit_task("SAT-1", now, now + timedelta(minutes=10),
                                       100.0, TaskPriority.LOW)
        task_b = scheduler.submit_task("SAT-1", now, now + timedelta(minutes=10),
                                       100.0, TaskPriority.CRITICAL)

        winner = scheduler.resolve_conflict(task_a, task_b)
        assert winner.task_id == task_b.task_id

    def test_tie_broken_by_submission_time(self, scheduler):
        now = datetime.utcnow()
        task_a = scheduler.submit_task("SAT-1", now, now + timedelta(minutes=10),
                                       100.0, TaskPriority.HIGH)
        task_b = scheduler.submit_task("SAT-1", now, now + timedelta(minutes=10),
                                       100.0, TaskPriority.HIGH)

        winner = scheduler.resolve_conflict(task_a, task_b)
        assert winner.task_id == task_a.task_id  # earlier submission wins


class TestTaskCompletion:
    def test_complete_task_frees_station(self, scheduler, station_manager):
        make_task(scheduler)
        station = station_manager.get_station("GS-001")
        task = scheduler.assign_next_task(station)

        scheduler.complete_task(task.task_id, station)

        assert task.status == TaskStatus.COMPLETED
        assert station.status == StationStatus.IDLE
        assert station.tasks_completed == 1


class TestAuditLog:
    def test_audit_log_records_events(self, scheduler, station_manager):
        make_task(scheduler)
        station = station_manager.get_station("GS-001")
        task = scheduler.assign_next_task(station)
        scheduler.complete_task(task.task_id, station)

        log = scheduler.get_audit_log()
        event_types = [e["event_type"] for e in log]

        assert "TASK_SUBMITTED" in event_types
        assert "TASK_ASSIGNED" in event_types
        assert "TASK_COMPLETED" in event_types
