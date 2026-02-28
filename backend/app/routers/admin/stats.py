from datetime import datetime, timedelta
from typing import Optional
import math

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


@router.get("/patients")
async def get_admin_patients(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
):
    """Get paginated list of patients with static data."""
    # Static patients data
    all_patients = [
        {
            "id": "pat-001",
            "name": "Rajesh Kumar",
            "photo": None,
            "status": "completed",
            "statusLabel": "Treated",
            "lastVisit": "2026-02-25",
            "gender": "Male",
            "location": "Mumbai, Maharashtra",
            "doctor": "Dr. Priya Sharma",
            "department": "Cardiology",
            "age": 45,
            "bloodType": "O+",
            "phone": "+91 98765 43210",
            "email": "rajesh.kumar@email.com",
            "address": "123 Marine Drive",
            "city": "Mumbai",
            "state": "Maharashtra",
            "zipCode": "400001",
            "emergencyContact": "Sunita Kumar",
            "emergencyPhone": "+91 98765 43211",
        },
        {
            "id": "pat-002",
            "name": "Anita Desai",
            "photo": None,
            "status": "inProgress",
            "statusLabel": "Under Treatment",
            "lastVisit": "2026-02-27",
            "gender": "Female",
            "location": "Delhi, Delhi",
            "doctor": "Dr. Arjun Patel",
            "department": "Orthopedics",
            "age": 52,
            "bloodType": "A+",
            "phone": "+91 98765 43220",
            "email": "anita.desai@email.com",
            "address": "456 Connaught Place",
            "city": "Delhi",
            "state": "Delhi",
            "zipCode": "110001",
            "emergencyContact": "Ramesh Desai",
            "emergencyPhone": "+91 98765 43221",
        },
        {
            "id": "pat-003",
            "name": "Mohammed Ali",
            "photo": None,
            "status": "pending",
            "statusLabel": "Awaiting Consultation",
            "lastVisit": "2026-02-20",
            "gender": "Male",
            "location": "Bangalore, Karnataka",
            "doctor": "Dr. Sanjay Gupta",
            "department": "General Medicine",
            "age": 38,
            "bloodType": "B+",
            "phone": "+91 98765 43230",
            "email": "mohammed.ali@email.com",
            "address": "789 MG Road",
            "city": "Bangalore",
            "state": "Karnataka",
            "zipCode": "560001",
            "emergencyContact": "Fatima Ali",
            "emergencyPhone": "+91 98765 43231",
        },
        {
            "id": "pat-004",
            "name": "Lakshmi Iyer",
            "photo": None,
            "status": "completed",
            "statusLabel": "Treated",
            "lastVisit": "2026-02-24",
            "gender": "Female",
            "location": "Chennai, Tamil Nadu",
            "doctor": "Dr. Meera Nair",
            "department": "Pediatrics",
            "age": 29,
            "bloodType": "AB+",
            "phone": "+91 98765 43240",
            "email": "lakshmi.iyer@email.com",
            "address": "321 Anna Salai",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "zipCode": "600002",
            "emergencyContact": "Ravi Iyer",
            "emergencyPhone": "+91 98765 43241",
        },
        {
            "id": "pat-005",
            "name": "Vikram Singh",
            "photo": None,
            "status": "inProgress",
            "statusLabel": "Under Treatment",
            "lastVisit": "2026-02-26",
            "gender": "Male",
            "location": "Jaipur, Rajasthan",
            "doctor": "Dr. Kavita Reddy",
            "department": "Dermatology",
            "age": 41,
            "bloodType": "O-",
            "phone": "+91 98765 43250",
            "email": "vikram.singh@email.com",
            "address": "654 MI Road",
            "city": "Jaipur",
            "state": "Rajasthan",
            "zipCode": "302001",
            "emergencyContact": "Neha Singh",
            "emergencyPhone": "+91 98765 43251",
        },
        {
            "id": "pat-006",
            "name": "Priya Menon",
            "photo": None,
            "status": "completed",
            "statusLabel": "Treated",
            "lastVisit": "2026-02-23",
            "gender": "Female",
            "location": "Kochi, Kerala",
            "doctor": "Dr. Rajesh Kumar",
            "department": "Gynecology",
            "age": 34,
            "bloodType": "A-",
            "phone": "+91 98765 43260",
            "email": "priya.menon@email.com",
            "address": "987 MG Road",
            "city": "Kochi",
            "state": "Kerala",
            "zipCode": "682001",
            "emergencyContact": "Suresh Menon",
            "emergencyPhone": "+91 98765 43261",
        },
        {
            "id": "pat-007",
            "name": "Amit Shah",
            "photo": None,
            "status": "pending",
            "statusLabel": "Awaiting Consultation",
            "lastVisit": "2026-02-19",
            "gender": "Male",
            "location": "Ahmedabad, Gujarat",
            "doctor": "Dr. Neha Kapoor",
            "department": "Neurology",
            "age": 56,
            "bloodType": "B-",
            "phone": "+91 98765 43270",
            "email": "amit.shah@email.com",
            "address": "147 CG Road",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "zipCode": "380009",
            "emergencyContact": "Ritu Shah",
            "emergencyPhone": "+91 98765 43271",
        },
        {
            "id": "pat-008",
            "name": "Sneha Reddy",
            "photo": None,
            "status": "inProgress",
            "statusLabel": "Under Treatment",
            "lastVisit": "2026-02-28",
            "gender": "Female",
            "location": "Hyderabad, Telangana",
            "doctor": "Dr. Anil Kumar",
            "department": "Endocrinology",
            "age": 47,
            "bloodType": "O+",
            "phone": "+91 98765 43280",
            "email": "sneha.reddy@email.com",
            "address": "258 Banjara Hills",
            "city": "Hyderabad",
            "state": "Telangana",
            "zipCode": "500034",
            "emergencyContact": "Krishna Reddy",
            "emergencyPhone": "+91 98765 43281",
        },
        {
            "id": "pat-009",
            "name": "Arjun Nair",
            "photo": None,
            "status": "completed",
            "statusLabel": "Treated",
            "lastVisit": "2026-02-22",
            "gender": "Male",
            "location": "Pune, Maharashtra",
            "doctor": "Dr. Shalini Desai",
            "department": "Ophthalmology",
            "age": 33,
            "bloodType": "A+",
            "phone": "+91 98765 43290",
            "email": "arjun.nair@email.com",
            "address": "369 FC Road",
            "city": "Pune",
            "state": "Maharashtra",
            "zipCode": "411004",
            "emergencyContact": "Maya Nair",
            "emergencyPhone": "+91 98765 43291",
        },
        {
            "id": "pat-010",
            "name": "Kavita Sharma",
            "photo": None,
            "status": "pending",
            "statusLabel": "Awaiting Consultation",
            "lastVisit": "2026-02-18",
            "gender": "Female",
            "location": "Lucknow, Uttar Pradesh",
            "doctor": "Dr. Vivek Pandey",
            "department": "Psychiatry",
            "age": 39,
            "bloodType": "AB-",
            "phone": "+91 98765 43300",
            "email": "kavita.sharma@email.com",
            "address": "741 Hazratganj",
            "city": "Lucknow",
            "state": "Uttar Pradesh",
            "zipCode": "226001",
            "emergencyContact": "Rohit Sharma",
            "emergencyPhone": "+91 98765 43301",
        },
        {
            "id": "pat-011",
            "name": "Ravi Verma",
            "photo": None,
            "status": "inProgress",
            "statusLabel": "Under Treatment",
            "lastVisit": "2026-02-27",
            "gender": "Male",
            "location": "Kolkata, West Bengal",
            "doctor": "Dr. Anjali Sen",
            "department": "Urology",
            "age": 61,
            "bloodType": "B+",
            "phone": "+91 98765 43310",
            "email": "ravi.verma@email.com",
            "address": "852 Park Street",
            "city": "Kolkata",
            "state": "West Bengal",
            "zipCode": "700016",
            "emergencyContact": "Geeta Verma",
            "emergencyPhone": "+91 98765 43311",
        },
        {
            "id": "pat-012",
            "name": "Deepa Patel",
            "photo": None,
            "status": "completed",
            "statusLabel": "Treated",
            "lastVisit": "2026-02-21",
            "gender": "Female",
            "location": "Surat, Gujarat",
            "doctor": "Dr. Manish Joshi",
            "department": "Rheumatology",
            "age": 44,
            "bloodType": "O-",
            "phone": "+91 98765 43320",
            "email": "deepa.patel@email.com",
            "address": "963 Ring Road",
            "city": "Surat",
            "state": "Gujarat",
            "zipCode": "395002",
            "emergencyContact": "Kiran Patel",
            "emergencyPhone": "+91 98765 43321",
        },
    ]

    # Apply search filter
    filtered_patients = all_patients
    if search:
        search_lower = search.lower()
        filtered_patients = [
            p for p in all_patients
            if search_lower in p["name"].lower()
            or search_lower in p["email"].lower()
            or search_lower in p["phone"]
        ]

    # Apply status filter
    if status:
        filtered_patients = [p for p in filtered_patients if p["status"] == status]

    # Calculate pagination
    total = len(filtered_patients)
    total_pages = math.ceil(total / limit)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_patients = filtered_patients[start_idx:end_idx]

    return {
        "patients": paginated_patients,
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": total_pages,
    }
