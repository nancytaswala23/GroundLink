import heapq
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from models.models import (
    DownlinkTask,
    GroundStation,
    StationStatus,
    TaskPriority,
    TaskStatus,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Priority queue-based scheduler for satellite downlink tasks.
    Handles conflict resolution and auto-reassignment on station failure.
    """

    def __init__(self):
        self._queue: List[Tuple[int, DownlinkTask]] = []  # min-heap (negated priority)
        self._task_registry: Dict[str, DownlinkTask] = {}
        self._audit_log: List[dict] = []

    def submit_task(
        self,
        satellite_id: str,
        window_start: datetime,
        window_end: datetime,
        data_volume_mb: float,
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> DownlinkTask:
        """Submit a new downlink task to the scheduler queue."""
        task = DownlinkTask(
            priority=-priority.value,  # negate for max-heap behavior
            task_id=str(uuid.uuid4()),
            satellite_id=satellite_id,
            window_start=window_start,
            window_end=window_end,
            data_volume_mb=data_volume_mb,
        )
        heapq.heappush(self._queue, (task.priority, task))
        self._task_registry[task.task_id] = task
        self._log_event("TASK_SUBMITTED", task.task_id, details=f"Priority: {priority.name}")
        logger.info(f"Task {task.task_id} submitted for satellite {satellite_id}")
        return task

    def assign_next_task(self, station: GroundStation) -> Optional[DownlinkTask]:
        """Assign the highest priority pending task to an available station."""
        if not station.is_available():
            logger.warning(f"Station {station.station_id} is not available")
            return None

        while self._queue:
            _, task = heapq.heappop(self._queue)
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.ASSIGNED
                task.assigned_station = station.station_id
                station.status = StationStatus.BUSY
                station.current_task = task.task_id
                self._log_event("TASK_ASSIGNED", task.task_id, station.station_id)
                logger.info(f"Task {task.task_id} assigned to station {station.station_id}")
                return task

        return None

    def complete_task(self, task_id: str, station: GroundStation) -> bool:
        """Mark a task as completed and free the station."""
        task = self._task_registry.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        station.status = StationStatus.IDLE
        station.current_task = None
        station.tasks_completed += 1
        self._log_event("TASK_COMPLETED", task_id, station.station_id)
        logger.info(f"Task {task_id} completed by station {station.station_id}")
        return True

    def handle_station_failure(
        self,
        failed_station: GroundStation,
        all_stations: Dict[str, GroundStation],
    ) -> Optional[DownlinkTask]:
        """
        Handle station failure: mark station as failed,
        retrieve its task, and reassign to next available station.
        """
        failed_station.status = StationStatus.FAILED
        failed_station.tasks_failed += 1
        task_id = failed_station.current_task
        failed_station.current_task = None

        if not task_id:
            logger.warning(f"Station {failed_station.station_id} failed with no active task")
            return None

        task = self._task_registry.get(task_id)
        if not task:
            return None

        self._log_event("STATION_FAILED", task_id, failed_station.station_id)
        logger.warning(f"Station {failed_station.station_id} failed — reassigning task {task_id}")

        # Find next available station (exclude failed one)
        for station_id, station in all_stations.items():
            if station_id != failed_station.station_id and station.is_available():
                task.status = TaskStatus.REASSIGNED
                task.retry_count += 1
                task.assigned_station = station.station_id
                station.status = StationStatus.BUSY
                station.current_task = task.task_id
                self._log_event("TASK_REASSIGNED", task_id, station.station_id,
                                details=f"Retry #{task.retry_count}")
                logger.info(f"Task {task_id} reassigned to station {station.station_id}")
                return task

        # No available station — requeue with elevated priority
        task.status = TaskStatus.PENDING
        task.assigned_station = None
        elevated_priority = min(task.priority - 1, -TaskPriority.CRITICAL.value)
        heapq.heappush(self._queue, (elevated_priority, task))
        self._log_event("TASK_REQUEUED", task_id, details="No available station — priority elevated")
        logger.warning(f"Task {task_id} requeued — no available stations")
        return None

    def resolve_conflict(
        self,
        task_a: DownlinkTask,
        task_b: DownlinkTask,
    ) -> DownlinkTask:
        """
        Resolve scheduling conflict between two tasks competing
        for the same satellite window. Higher priority wins.
        Ties broken by earlier submission time.
        """
        if task_a.priority < task_b.priority:  # remember: negated
            winner, loser = task_a, task_b
        elif task_b.priority < task_a.priority:
            winner, loser = task_b, task_a
        else:
            # Tie-break: earlier created_at wins
            winner = task_a if task_a.created_at <= task_b.created_at else task_b
            loser = task_b if winner == task_a else task_a

        loser.status = TaskStatus.PENDING
        loser.assigned_station = None
        heapq.heappush(self._queue, (loser.priority, loser))
        self._log_event("CONFLICT_RESOLVED", winner.task_id,
                        details=f"Won over {loser.task_id}")
        logger.info(f"Conflict resolved: {winner.task_id} wins over {loser.task_id}")
        return winner

    def get_queue_snapshot(self) -> List[dict]:
        """Return current queue state without mutating it."""
        return [task.to_dict() for _, task in sorted(self._queue)]

    def get_audit_log(self) -> List[dict]:
        return self._audit_log

    def _log_event(
        self,
        event_type: str,
        task_id: str,
        station_id: Optional[str] = None,
        details: Optional[str] = None,
    ):
        self._audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "task_id": task_id,
            "station_id": station_id,
            "details": details,
        })
