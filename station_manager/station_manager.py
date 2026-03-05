import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.models import GroundStation, StationStatus

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_SECONDS = 30


class StationManager:
    """
    Manages the registry of ground stations.
    Tracks status, heartbeats, and detects failed stations.
    """

    def __init__(self):
        self._stations: Dict[str, GroundStation] = {}

    def register_station(
        self,
        location: str,
        capacity_mbps: float,
        station_id: Optional[str] = None,
    ) -> GroundStation:
        """Register a new ground station."""
        sid = station_id or f"GS-{str(uuid.uuid4())[:8].upper()}"
        station = GroundStation(
            station_id=sid,
            location=location,
            capacity_mbps=capacity_mbps,
        )
        self._stations[sid] = station
        logger.info(f"Station {sid} registered at {location}")
        return station

    def get_station(self, station_id: str) -> Optional[GroundStation]:
        return self._stations.get(station_id)

    def get_all_stations(self) -> Dict[str, GroundStation]:
        return self._stations

    def get_available_stations(self) -> List[GroundStation]:
        return [s for s in self._stations.values() if s.is_available()]

    def heartbeat(self, station_id: str) -> bool:
        """Update station heartbeat timestamp."""
        station = self._stations.get(station_id)
        if not station:
            return False
        station.last_heartbeat = datetime.utcnow()
        if station.status == StationStatus.FAILED:
            station.status = StationStatus.IDLE
            logger.info(f"Station {station_id} recovered via heartbeat")
        return True

    def detect_failed_stations(self) -> List[GroundStation]:
        """
        Detect stations that have missed heartbeats.
        Returns list of newly failed stations.
        """
        now = datetime.utcnow()
        failed = []
        for station in self._stations.values():
            if station.status == StationStatus.FAILED:
                continue
            elapsed = (now - station.last_heartbeat).total_seconds()
            if elapsed > HEARTBEAT_TIMEOUT_SECONDS:
                station.status = StationStatus.FAILED
                logger.warning(
                    f"Station {station.station_id} marked FAILED "
                    f"(no heartbeat for {elapsed:.0f}s)"
                )
                failed.append(station)
        return failed

    def simulate_failure(self, station_id: str) -> bool:
        """Force a station into failed state (for testing)."""
        station = self._stations.get(station_id)
        if not station:
            return False
        station.status = StationStatus.FAILED
        logger.warning(f"Station {station_id} manually set to FAILED")
        return True

    def get_summary(self) -> dict:
        stations = list(self._stations.values())
        return {
            "total": len(stations),
            "idle": sum(1 for s in stations if s.status == StationStatus.IDLE),
            "busy": sum(1 for s in stations if s.status == StationStatus.BUSY),
            "failed": sum(1 for s in stations if s.status == StationStatus.FAILED),
            "stations": [s.to_dict() for s in stations],
        }
