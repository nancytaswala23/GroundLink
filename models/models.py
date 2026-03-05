from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional


class StationStatus(Enum):
    ACTIVE = "active"
    FAILED = "failed"
    BUSY = "busy"
    IDLE = "idle"


class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REASSIGNED = "reassigned"


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(order=True)
class DownlinkTask:
    """Represents a satellite downlink window task."""
    priority: int
    task_id: str = field(compare=False)
    satellite_id: str = field(compare=False)
    window_start: datetime = field(compare=False)
    window_end: datetime = field(compare=False)
    data_volume_mb: float = field(compare=False)
    status: TaskStatus = field(default=TaskStatus.PENDING, compare=False)
    assigned_station: Optional[str] = field(default=None, compare=False)
    created_at: datetime = field(default_factory=datetime.utcnow, compare=False)
    completed_at: Optional[datetime] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "satellite_id": self.satellite_id,
            "priority": self.priority,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "data_volume_mb": self.data_volume_mb,
            "status": self.status.value,
            "assigned_station": self.assigned_station,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
        }


@dataclass
class GroundStation:
    """Represents a ground station node."""
    station_id: str
    location: str
    capacity_mbps: float
    status: StationStatus = StationStatus.IDLE
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)

    def is_available(self) -> bool:
        return self.status == StationStatus.IDLE

    def to_dict(self) -> dict:
        return {
            "station_id": self.station_id,
            "location": self.location,
            "capacity_mbps": self.capacity_mbps,
            "status": self.status.value,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }
