from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies import require_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin", "stats"])


@router.get("/stats")
async def get_dashboard_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get dashboard statistics with static data."""
    return {
        "total_patients": 1247,
        "total_appointments": 3892,
        "total_doctors": 87,
        "total_transactions": 15634,
        "patient_trend": 12.5,  # +12.5% increase
        "appointment_trend": 8.3,  # +8.3% increase
        "doctor_trend": 5.2,  # +5.2% increase
        "transaction_trend": 18.7,  # +18.7% increase
    }


@router.get("/stats/patient-trend")
async def get_patient_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get patient trend data for sparklines (last 30 days)."""
    # Generate 30 days of data with upward trend
    today = datetime.now()
    trend = []

    base_value = 1150
    for i in range(30):
        date = today - timedelta(days=29 - i)
        # Add some variance and upward trend
        value = base_value + (i * 3) + ((-1) ** i * 5)
        trend.append({"date": date.strftime("%Y-%m-%d"), "value": value})

    return {"trend": trend}


@router.get("/stats/appointment-trend")
async def get_appointment_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get appointment trend data for sparklines (last 30 days)."""
    today = datetime.now()
    trend = []

    base_value = 3600
    for i in range(30):
        date = today - timedelta(days=29 - i)
        # Add some variance and upward trend
        value = base_value + (i * 10) + ((-1) ** i * 20)
        trend.append({"date": date.strftime("%Y-%m-%d"), "value": value})

    return {"trend": trend}


@router.get("/stats/doctor-trend")
async def get_doctor_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get doctor trend data for sparklines (last 30 days)."""
    today = datetime.now()
    trend = []

    base_value = 82
    for i in range(30):
        date = today - timedelta(days=29 - i)
        # Slow growth for doctors
        value = base_value + (i // 6)  # +1 every 6 days
        trend.append({"date": date.strftime("%Y-%m-%d"), "value": value})

    return {"trend": trend}


@router.get("/stats/transaction-trend")
async def get_transaction_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get transaction trend data for sparklines (last 30 days)."""
    today = datetime.now()
    trend = []

    base_value = 13000
    for i in range(30):
        date = today - timedelta(days=29 - i)
        # Higher variance and strong upward trend
        value = base_value + (i * 88) + ((-1) ** i * 150)
        trend.append({"date": date.strftime("%Y-%m-%d"), "value": value})

    return {"trend": trend}


@router.get("/stats/patient-statistics")
async def get_patient_statistics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get patient statistics (new vs returning patients) for the last 7 days."""
    today = datetime.now()
    statistics = []

    for i in range(7):
        date = today - timedelta(days=6 - i)
        # Generate realistic new vs returning patient counts
        new_patients = 15 + (i * 2) + ((-1) ** i * 3)
        returning_patients = 45 + (i * 5) + ((-1) ** i * 8)

        statistics.append({
            "date": date.strftime("%Y-%m-%d"),
            "new_patients": max(new_patients, 10),  # At least 10
            "returning_patients": max(returning_patients, 30),  # At least 30
        })

    return {"statistics": statistics}


@router.get("/appointment-requests")
async def get_appointment_requests(
    limit: int = Query(5, ge=1, le=50),
    admin: User = Depends(require_admin),
):
    """Get pending appointment requests with static data."""
    # Static appointment requests data
    requests = [
        {
            "id": "req-001",
            "patient_id": "patient-001",
            "patient_name": "Rajesh Kumar",
            "patient_photo": None,
            "doctor_id": "doctor-001",
            "doctor_name": "Dr. Priya Sharma",
            "department": "Cardiology",
            "requested_date": "2026-03-01",
            "requested_time": "10:00 AM",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
        },
        {
            "id": "req-002",
            "patient_id": "patient-002",
            "patient_name": "Anita Desai",
            "patient_photo": None,
            "doctor_id": "doctor-002",
            "doctor_name": "Dr. Arjun Patel",
            "department": "Orthopedics",
            "requested_date": "2026-03-01",
            "requested_time": "02:30 PM",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=5)).isoformat(),
        },
        {
            "id": "req-003",
            "patient_id": "patient-003",
            "patient_name": "Mohammed Ali",
            "patient_photo": None,
            "doctor_id": "doctor-003",
            "doctor_name": "Dr. Sanjay Gupta",
            "department": "General Medicine",
            "requested_date": "2026-03-02",
            "requested_time": "11:00 AM",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=8)).isoformat(),
        },
        {
            "id": "req-004",
            "patient_id": "patient-004",
            "patient_name": "Lakshmi Iyer",
            "patient_photo": None,
            "doctor_id": "doctor-004",
            "doctor_name": "Dr. Meera Nair",
            "department": "Pediatrics",
            "requested_date": "2026-03-02",
            "requested_time": "03:00 PM",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=12)).isoformat(),
        },
        {
            "id": "req-005",
            "patient_id": "patient-005",
            "patient_name": "Vikram Singh",
            "patient_photo": None,
            "doctor_id": "doctor-005",
            "doctor_name": "Dr. Kavita Reddy",
            "department": "Dermatology",
            "requested_date": "2026-03-03",
            "requested_time": "09:30 AM",
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=18)).isoformat(),
        },
    ]

    # Return limited number of requests
    return {"requests": requests[:limit]}
