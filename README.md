# 🛰️ GroundLink

**Distributed Ground Station Task Scheduler for Satellite Downlink Windows**

[![CI](https://github.com/nancytaswala23/groundlink/actions/workflows/ci.yml/badge.svg)](https://github.com/nancytaswala23/groundlink/actions)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)

---

## 📡 Overview

GroundLink is a distributed task scheduling system that manages satellite downlink window assignments across a network of ground stations. When a satellite passes overhead, ground stations compete for the downlink window — GroundLink ensures the highest-priority task wins, handles station failures automatically, and maintains a full audit trail of every scheduling decision.

Inspired by real ground station coordination challenges in low Earth orbit satellite networks (e.g., Amazon Kuiper/Leo).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     GroundLink System                    │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  FastAPI     │    │  Task        │                   │
│  │  REST API    │───▶│  Scheduler   │                   │
│  │  :8000       │    │  (Priority   │                   │
│  └──────────────┘    │   Queue)     │                   │
│         │            └──────┬───────┘                   │
│         │                   │                           │
│         ▼            ┌──────▼───────┐                   │
│  ┌──────────────┐    │  Station     │                   │
│  │  Station     │◀───│  Manager     │                   │
│  │  Registry    │    │  (Heartbeat  │                   │
│  │  GS-ALASKA   │    │   Monitor)   │                   │
│  │  GS-CHILE    │    └──────────────┘                   │
│  │  GS-PERTH    │                                       │
│  │  GS-SVALBARD │    ┌──────────────┐                   │
│  └──────────────┘    │  Audit Log   │                   │
│                      │  (PostgreSQL │                   │
│                      │   ready)     │                   │
│                      └──────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

- **Priority Queue Scheduling** — CRITICAL > HIGH > MEDIUM > LOW, ties broken by submission time
- **Auto Fault Tolerance** — station failure triggers instant reassignment to next available station
- **Conflict Resolution** — two stations competing for same window → higher priority wins
- **Heartbeat Monitoring** — stations missing heartbeats are auto-detected and marked failed
- **Full Audit Trail** — every scheduling event logged with timestamp, task ID, station ID
- **REST API** — full FastAPI service with health check, task submission, assignment, and dashboard endpoints
- **CI/CD** — GitHub Actions runs tests on every push

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/nancytaswala23/groundlink.git
cd groundlink

# Run with Docker
docker-compose up --build

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## 📮 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/tasks/submit` | Submit a downlink task |
| POST | `/tasks/assign` | Assign next task to a station |
| POST | `/tasks/{id}/complete` | Mark task completed |
| POST | `/stations/simulate-failure/{id}` | Simulate station failure |
| POST | `/stations/heartbeat` | Station heartbeat |
| GET | `/stations` | All stations + status |
| GET | `/queue` | Current task queue |
| GET | `/audit-log` | Full scheduling audit log |

---

## 🧪 Example Flow

```bash
# 1. Submit a CRITICAL priority downlink task
curl -X POST http://localhost:8000/tasks/submit \
  -H "Content-Type: application/json" \
  -d '{"satellite_id": "KP-SAT-001", "data_volume_mb": 500, "priority": "CRITICAL"}'

# 2. Assign to a ground station
curl -X POST http://localhost:8000/tasks/assign \
  -H "Content-Type: application/json" \
  -d '{"station_id": "GS-ALASKA"}'

# 3. Simulate station failure → auto-reassignment kicks in
curl -X POST http://localhost:8000/stations/simulate-failure/GS-ALASKA

# 4. View full audit log
curl http://localhost:8000/audit-log
```

---

## 🗂️ Project Structure

```
groundlink/
├── api/
│   └── main.py              # FastAPI REST layer
├── scheduler/
│   └── scheduler.py         # Priority queue + conflict resolution + fault tolerance
├── station_manager/
│   └── station_manager.py   # Station registry + heartbeat monitoring
├── models/
│   └── models.py            # Core data classes (OOP)
├── tests/
│   └── test_groundlink.py   # Full test suite
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🔧 Core Algorithms

- **Priority Queue** (`heapq`) — O(log n) task insertion and extraction
- **Conflict Resolution** — priority comparison with timestamp tie-breaking
- **Fault Tolerance** — O(n) station scan on failure, priority elevation on requeue
- **Heartbeat Detection** — timestamp delta comparison against configurable timeout

---

## 🌍 Real-World Relevance

This system mirrors ground station coordination challenges in LEO satellite networks where:
- Multiple satellites have limited downlink windows per orbit
- Ground stations can fail due to weather, power, or hardware issues
- Mission-critical data (emergency comms, navigation) must be prioritized
- Every scheduling decision must be auditable for operations teams
