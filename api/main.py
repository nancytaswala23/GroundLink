import sys
sys.path.insert(0, "/app")

from datetime import datetime, timedelta
from typing import Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from models.models import TaskPriority
from scheduler.scheduler import TaskScheduler
from station_manager.station_manager import StationManager

app = FastAPI(
    title="GroundLink API",
    description="Distributed Ground Station Task Scheduler for Satellite Downlink Windows",
    version="1.0.0",
)

scheduler = TaskScheduler()
station_manager = StationManager()


# ── Seed some ground stations on startup ──────────────────────────────────────
@app.on_event("startup")
def seed_stations():
    station_manager.register_station("Fairbanks, Alaska", 500.0, "GS-ALASKA")
    station_manager.register_station("Punta Arenas, Chile", 300.0, "GS-CHILE")
    station_manager.register_station("Perth, Australia", 400.0, "GS-PERTH")
    station_manager.register_station("Svalbard, Norway", 350.0, "GS-SVALBARD")


# ── Request / Response schemas ────────────────────────────────────────────────
class TaskRequest(BaseModel):
    satellite_id: str
    data_volume_mb: float
    priority: str = "MEDIUM"
    window_duration_minutes: int = 10


class AssignRequest(BaseModel):
    station_id: str


class HeartbeatRequest(BaseModel):
    station_id: str


class RegisterStationRequest(BaseModel):
    location: str
    capacity_mbps: float
    station_id: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/tasks/submit")
def submit_task(req: TaskRequest):
    """Submit a new satellite downlink task to the scheduler queue."""
    try:
        priority = TaskPriority[req.priority.upper()]
    except KeyError:
        raise HTTPException(400, f"Invalid priority. Choose from: {[p.name for p in TaskPriority]}")

    now = datetime.utcnow()
    task = scheduler.submit_task(
        satellite_id=req.satellite_id,
        window_start=now,
        window_end=now + timedelta(minutes=req.window_duration_minutes),
        data_volume_mb=req.data_volume_mb,
        priority=priority,
    )
    return {"message": "Task submitted", "task": task.to_dict()}


@app.post("/tasks/assign")
def assign_task(req: AssignRequest):
    """Assign the next highest priority task to a ground station."""
    station = station_manager.get_station(req.station_id)
    if not station:
        raise HTTPException(404, f"Station {req.station_id} not found")

    task = scheduler.assign_next_task(station)
    if not task:
        return {"message": "No pending tasks or station unavailable"}

    return {"message": "Task assigned", "task": task.to_dict()}


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, req: AssignRequest):
    """Mark a task as completed."""
    station = station_manager.get_station(req.station_id)
    if not station:
        raise HTTPException(404, f"Station {req.station_id} not found")

    success = scheduler.complete_task(task_id, station)
    if not success:
        raise HTTPException(404, f"Task {task_id} not found")

    return {"message": "Task completed", "task_id": task_id}


@app.post("/stations/simulate-failure/{station_id}")
def simulate_failure(station_id: str):
    """Simulate a station failure and trigger auto-reassignment."""
    station = station_manager.get_station(station_id)
    if not station:
        raise HTTPException(404, f"Station {station_id} not found")

    all_stations = station_manager.get_all_stations()
    reassigned = scheduler.handle_station_failure(station, all_stations)

    return {
        "message": f"Station {station_id} failed",
        "reassigned_task": reassigned.to_dict() if reassigned else None,
    }


@app.post("/stations/heartbeat")
def heartbeat(req: HeartbeatRequest):
    """Station sends heartbeat to signal it's alive."""
    success = station_manager.heartbeat(req.station_id)
    if not success:
        raise HTTPException(404, f"Station {req.station_id} not found")
    return {"message": "Heartbeat received", "station_id": req.station_id}


@app.post("/stations/register")
def register_station(req: RegisterStationRequest):
    """Register a new ground station."""
    station = station_manager.register_station(
        req.location, req.capacity_mbps, req.station_id
    )
    return {"message": "Station registered", "station": station.to_dict()}


@app.get("/stations")
def get_stations():
    """Get all ground stations and their current status."""
    return station_manager.get_summary()


@app.get("/queue")
def get_queue():
    """Get current task queue snapshot."""
    return {"queue": scheduler.get_queue_snapshot()}


@app.get("/audit-log")
def get_audit_log():
    """Get full audit log of all scheduling events."""
    return {"audit_log": scheduler.get_audit_log()}


@app.get("/stations/detect-failures")
def detect_failures():
    """Detect and return stations that have missed heartbeats."""
    failed = station_manager.detect_failed_stations()
    return {
        "failed_stations": [s.to_dict() for s in failed],
        "count": len(failed),
    }


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
