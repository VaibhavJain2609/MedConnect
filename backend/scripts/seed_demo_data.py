#!/usr/bin/env python3
"""
Seed demo data for local development and demos.

Creates a small, self-consistent dataset in the main application database:

- 1 admin user
- 2 doctor users with verified, fully-onboarded Doctor profiles
- 1 clinic + 1 branch + ClinicMemberships for both doctors
- 3 patient users with approved PatientClinicLinks
- 5 appointments across today/tomorrow (varied statuses)
- 2 queue entries for today
- 2 notifications

Idempotent: all lookups are keyed (users by email, children by FK pairs,
appointments by patient+doctor+scheduled_at). Running it twice creates no
duplicates.

Usage:
    cd backend && python scripts/seed_demo_data.py          # seed (idempotent)
    cd backend && python scripts/seed_demo_data.py --drop   # delete seeded rows

Honours DATABASE_URL (default: the compose value from app.config). Seeded
users get placeholder keycloak_sub values ('seed-admin-1', ...) — real login
requires matching Keycloak users; see docs/seed.md.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, func, or_, select

from app.database import async_session
from app.models import (
    Appointment,
    Clinic,
    ClinicBranch,
    ClinicMembership,
    Doctor,
    Notification,
    NotificationType,
    PatientClinicLink,
    User,
)
from app.models.queue import QueueEntry

# --- seed specification ------------------------------------------------------

CLINIC_EMAIL = "clinic@medconnect.demo"
CLINIC_NAME = "Sunrise Family Clinic (Demo)"
BRANCH_NAME = "Main Branch"

ADMIN_SPEC = {
    "email": "admin@medconnect.demo",
    "keycloak_sub": "seed-admin-1",
    "full_name": "Demo Admin",
    "role": "admin",
}

DOCTOR_SPECS = [
    {
        "user": {
            "email": "dr.priya@medconnect.demo",
            "keycloak_sub": "seed-doctor-1",
            "full_name": "Dr. Priya Sharma",
            "role": "doctor",
            "phone": "+919810000001",
        },
        "doctor": {
            "specialization": "General Medicine",
            "license_number": "DEMO-NMC-0001",
            "license_council": "National Medical Commission",
            "license_year": 2015,
            "facility_name": "Sunrise Family Clinic",
            "facility_city": "Bengaluru",
            "verified": True,
            "onboarding_step": "completed",
        },
        "membership_role": "owner",
    },
    {
        "user": {
            "email": "dr.arjun@medconnect.demo",
            "keycloak_sub": "seed-doctor-2",
            "full_name": "Dr. Arjun Mehta",
            "role": "doctor",
            "phone": "+919810000002",
        },
        "doctor": {
            "specialization": "Pediatrics",
            "license_number": "DEMO-NMC-0002",
            "license_council": "National Medical Commission",
            "license_year": 2018,
            "facility_name": "Sunrise Family Clinic",
            "facility_city": "Bengaluru",
            "verified": True,
            "onboarding_step": "completed",
        },
        "membership_role": "doctor",
    },
]

PATIENT_SPECS = [
    {
        "email": "rohan.verma@medconnect.demo",
        "keycloak_sub": "seed-patient-1",
        "full_name": "Rohan Verma",
        "role": "patient",
        "phone": "+919810000101",
        "blood_group": "O+",
    },
    {
        "email": "ananya.iyer@medconnect.demo",
        "keycloak_sub": "seed-patient-2",
        "full_name": "Ananya Iyer",
        "role": "patient",
        "phone": "+919810000102",
        "blood_group": "B+",
        "chronic_conditions": ["Type 2 Diabetes"],
    },
    {
        "email": "kabir.singh@medconnect.demo",
        "keycloak_sub": "seed-patient-3",
        "full_name": "Kabir Singh",
        "role": "patient",
        "phone": "+919810000103",
        "blood_group": "A-",
        "allergies": ["Penicillin"],
    },
]

SEED_USER_EMAILS = [ADMIN_SPEC["email"]] + [
    s["user"]["email"] for s in DOCTOR_SPECS
] + [s["email"] for s in PATIENT_SPECS]

# (patient_index, doctor_index, day_offset, hour, minute, type, status,
#  chief_complaint, extra)
APPOINTMENT_SPECS = [
    (0, 0, 0, 9, 0, "in-person", "completed", "Fever and sore throat", {}),
    (1, 0, 0, 10, 0, "in-person", "arrived", "Routine health checkup", {}),
    (2, 0, 0, 11, 30, "follow-up", "scheduled", "Diabetes follow-up", {}),
    (0, 1, 1, 10, 0, "teleconsult", "scheduled", "Child vaccination consult",
     {"meeting_url": "https://meet.jit.si/medconnect-demo-seed-1"}),
    (1, 1, 1, 15, 0, "in-person", "cancelled", "Skin rash",
     {"cancelled_reason": "Patient requested a reschedule"}),
]

NOTIFICATION_TITLES = ["Appointment confirmed", "New patient linked to clinic"]


class DemoSeeder:
    """Creates (or finds) the demo dataset idempotently."""

    def __init__(self, db):
        self.db = db
        self.stats: dict[str, dict[str, int]] = {}

    def _count(self, entity: str, created: bool):
        bucket = self.stats.setdefault(entity, {"created": 0, "skipped": 0})
        bucket["created" if created else "skipped"] += 1

    async def _get_or_create_user(self, spec: dict) -> User:
        result = await self.db.execute(
            select(User).where(User.email == spec["email"])
        )
        user = result.scalar_one_or_none()
        if user:
            self._count("users", False)
            return user
        user = User(is_active=True, **spec)
        self.db.add(user)
        await self.db.flush()
        self._count("users", True)
        return user

    async def _get_or_create_doctor(self, user: User, spec: dict) -> Doctor:
        result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == user.id, Doctor.deleted_at.is_(None)
            )
        )
        doctor = result.scalar_one_or_none()
        if doctor:
            self._count("doctors", False)
            return doctor
        doctor = Doctor(user_id=user.id, **spec)
        self.db.add(doctor)
        await self.db.flush()
        self._count("doctors", True)
        return doctor

    async def _get_or_create_clinic(self, admin: User) -> Clinic:
        result = await self.db.execute(
            select(Clinic).where(
                Clinic.email == CLINIC_EMAIL, Clinic.deleted_at.is_(None)
            )
        )
        clinic = result.scalar_one_or_none()
        if clinic:
            self._count("clinics", False)
            return clinic
        clinic = Clinic(
            name=CLINIC_NAME,
            email=CLINIC_EMAIL,
            address="12 MG Road",
            city="Bengaluru",
            state="Karnataka",
            phone="+918040000000",
            created_by=admin.id,
        )
        self.db.add(clinic)
        await self.db.flush()
        self._count("clinics", True)
        return clinic

    async def _get_or_create_branch(self, clinic: Clinic) -> ClinicBranch:
        result = await self.db.execute(
            select(ClinicBranch).where(
                ClinicBranch.clinic_id == clinic.id,
                ClinicBranch.name == BRANCH_NAME,
                ClinicBranch.deleted_at.is_(None),
            )
        )
        branch = result.scalar_one_or_none()
        if branch:
            self._count("clinic_branches", False)
            return branch
        branch = ClinicBranch(
            clinic_id=clinic.id,
            name=BRANCH_NAME,
            address="12 MG Road",
            city="Bengaluru",
            state="Karnataka",
            phone="+918040000000",
        )
        self.db.add(branch)
        await self.db.flush()
        self._count("clinic_branches", True)
        return branch

    async def _get_or_create_membership(
        self, clinic: Clinic, branch: ClinicBranch, user: User, role: str
    ) -> ClinicMembership:
        result = await self.db.execute(
            select(ClinicMembership).where(
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.user_id == user.id,
                ClinicMembership.deleted_at.is_(None),
            )
        )
        membership = result.scalar_one_or_none()
        if membership:
            self._count("clinic_memberships", False)
            return membership
        membership = ClinicMembership(
            clinic_id=clinic.id, branch_id=branch.id, user_id=user.id, role=role
        )
        self.db.add(membership)
        await self.db.flush()
        self._count("clinic_memberships", True)
        return membership

    async def _get_or_create_patient_link(
        self, patient: User, clinic: Clinic, linked_by: User
    ) -> PatientClinicLink:
        result = await self.db.execute(
            select(PatientClinicLink).where(
                PatientClinicLink.patient_id == patient.id,
                PatientClinicLink.clinic_id == clinic.id,
                PatientClinicLink.deleted_at.is_(None),
            )
        )
        link = result.scalar_one_or_none()
        if link:
            self._count("patient_clinic_links", False)
            return link
        link = PatientClinicLink(
            patient_id=patient.id,
            clinic_id=clinic.id,
            linked_by=linked_by.id,
            consent_status="approved",
            consented_at=datetime.now(timezone.utc),
        )
        self.db.add(link)
        await self.db.flush()
        self._count("patient_clinic_links", True)
        return link

    async def _get_or_create_appointment(
        self,
        patient: User,
        doctor: Doctor,
        clinic: Clinic,
        branch: ClinicBranch,
        creator: User,
        scheduled_at: datetime,
        appt_type: str,
        status: str,
        chief_complaint: str,
        extra: dict,
    ) -> Appointment:
        result = await self.db.execute(
            select(Appointment).where(
                Appointment.patient_id == patient.id,
                Appointment.doctor_id == doctor.id,
                Appointment.scheduled_at == scheduled_at,
                Appointment.deleted_at.is_(None),
            )
        )
        appt = result.scalar_one_or_none()
        if appt:
            self._count("appointments", False)
            return appt
        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            clinic_id=clinic.id,
            branch_id=branch.id,
            scheduled_at=scheduled_at,
            duration_minutes=30,
            type=appt_type,
            status=status,
            chief_complaint=chief_complaint,
            created_by=creator.id,
            **extra,
        )
        self.db.add(appt)
        await self.db.flush()
        self._count("appointments", True)
        return appt

    async def _next_queue_number(self, clinic: Clinic, today) -> int:
        result = await self.db.execute(
            select(func.max(QueueEntry.queue_number)).where(
                QueueEntry.clinic_id == clinic.id,
                QueueEntry.queue_date == today,
                QueueEntry.deleted_at.is_(None),
            )
        )
        return (result.scalar() or 0) + 1

    async def _get_or_create_queue_entry(
        self,
        clinic: Clinic,
        branch: ClinicBranch,
        patient: User,
        doctor: Doctor,
        appointment: Appointment | None,
        queue_number: int,
        status: str,
        notes: str | None = None,
    ) -> QueueEntry:
        # Keyed on the patient being in today's queue for this clinic.
        result = await self.db.execute(
            select(QueueEntry).where(
                QueueEntry.clinic_id == clinic.id,
                QueueEntry.patient_id == patient.id,
                QueueEntry.queue_date == datetime.now(timezone.utc).date(),
                QueueEntry.deleted_at.is_(None),
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            self._count("queue_entries", False)
            return entry
        now = datetime.now(timezone.utc)
        entry = QueueEntry(
            clinic_id=clinic.id,
            branch_id=branch.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_id=appointment.id if appointment else None,
            queue_number=queue_number,
            status=status,
            notes=notes,
            called_at=now if status == "in_consultation" else None,
        )
        self.db.add(entry)
        await self.db.flush()
        self._count("queue_entries", True)
        return entry

    async def _get_or_create_notification(
        self, user: User, ntype: NotificationType, title: str, message: str,
        action_url: str | None = None,
    ) -> Notification:
        result = await self.db.execute(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.title == title,
                Notification.deleted_at.is_(None),
            )
        )
        notif = result.scalar_one_or_none()
        if notif:
            self._count("notifications", False)
            return notif
        notif = Notification(
            user_id=user.id,
            type=ntype,
            title=title,
            message=message,
            action_url=action_url,
        )
        self.db.add(notif)
        await self.db.flush()
        self._count("notifications", True)
        return notif

    async def run(self):
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Users
        admin = await self._get_or_create_user(ADMIN_SPEC)
        doctor_users = []
        for spec in DOCTOR_SPECS:
            doctor_users.append(await self._get_or_create_user(spec["user"]))
        patients = [await self._get_or_create_user(s) for s in PATIENT_SPECS]

        # Doctor profiles
        doctors = []
        for user, spec in zip(doctor_users, DOCTOR_SPECS):
            doctors.append(await self._get_or_create_doctor(user, spec["doctor"]))

        # Clinic + branch + memberships
        clinic = await self._get_or_create_clinic(admin)
        branch = await self._get_or_create_branch(clinic)
        for user, spec in zip(doctor_users, DOCTOR_SPECS):
            await self._get_or_create_membership(
                clinic, branch, user, spec["membership_role"]
            )

        # Patient links (approved), linked by the clinic owner
        for patient in patients:
            await self._get_or_create_patient_link(
                patient, clinic, linked_by=doctor_users[0]
            )

        # Appointments
        appointments = []
        for (p_idx, d_idx, day_offset, hour, minute, appt_type, status,
             complaint, extra) in APPOINTMENT_SPECS:
            scheduled_at = today + timedelta(
                days=day_offset, hours=hour, minutes=minute
            )
            appointments.append(
                await self._get_or_create_appointment(
                    patients[p_idx], doctors[d_idx], clinic, branch, admin,
                    scheduled_at, appt_type, status, complaint, extra,
                )
            )

        # Queue entries for today: the "arrived" appointment is mid-consult,
        # the "scheduled" one is waiting.
        next_num = await self._next_queue_number(clinic, today.date())
        await self._get_or_create_queue_entry(
            clinic, branch, patients[1], doctors[0], appointments[1],
            next_num, "in_consultation",
        )
        await self._get_or_create_queue_entry(
            clinic, branch, patients[2], doctors[0], appointments[2],
            next_num + 1, "waiting", notes="Follow-up visit",
        )

        # Notifications
        await self._get_or_create_notification(
            patients[0], NotificationType.APPOINTMENT,
            NOTIFICATION_TITLES[0],
            "Your teleconsult with Dr. Arjun Mehta is confirmed for tomorrow.",
            action_url="/patient/appointments",
        )
        await self._get_or_create_notification(
            doctor_users[0], NotificationType.SYSTEM,
            NOTIFICATION_TITLES[1],
            "Kabir Singh has been linked to Sunrise Family Clinic (Demo).",
            action_url="/doctor/patients",
        )

        await self.db.commit()

    def print_summary(self):
        print("\n" + "=" * 60)
        print("SEED SUMMARY")
        print("=" * 60)
        for entity in sorted(self.stats):
            s = self.stats[entity]
            print(f"{entity:<24} created: {s['created']:<3} skipped: {s['skipped']}")
        print("=" * 60)
        print("Seeded user emails:")
        for email in SEED_USER_EMAILS:
            print(f"  - {email}")
        print("\nNote: keycloak_sub values are placeholders (seed-*); create matching")
        print("Keycloak users to log in as these accounts. See docs/seed.md.")


async def drop_seeded(db):
    """Hard-delete rows belonging to the seeded demo dataset.

    Matches seeded users by email and the clinic by its seeded email, then
    removes dependent rows in FK-safe order. Hard delete is intentional —
    soft deletes would leave the unique keycloak_sub values occupied and
    block re-seeding.
    """
    user_ids = (
        (await db.execute(select(User.id).where(User.email.in_(SEED_USER_EMAILS))))
        .scalars()
        .all()
    )
    doctor_ids = []
    if user_ids:
        doctor_ids = (
            (
                await db.execute(
                    select(Doctor.id).where(Doctor.user_id.in_(user_ids))
                )
            )
            .scalars()
            .all()
        )
    clinic_ids = (
        (await db.execute(select(Clinic.id).where(Clinic.email == CLINIC_EMAIL)))
        .scalars()
        .all()
    )
    appt_ids = []
    if user_ids or doctor_ids or clinic_ids:
        appt_ids = (
            (
                await db.execute(
                    select(Appointment.id).where(
                        or_(
                            Appointment.patient_id.in_(user_ids or []),
                            Appointment.doctor_id.in_(doctor_ids or []),
                            Appointment.clinic_id.in_(clinic_ids or []),
                            Appointment.created_by.in_(user_ids or []),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

    deleted: dict[str, int] = {}

    async def _del(entity, model, condition):
        result = await db.execute(delete(model).where(condition))
        deleted[entity] = result.rowcount or 0

    await _del(
        "queue_entries", QueueEntry,
        or_(
            QueueEntry.clinic_id.in_(clinic_ids or []),
            QueueEntry.patient_id.in_(user_ids or []),
            QueueEntry.appointment_id.in_(appt_ids or []),
        ),
    )
    await _del(
        "notifications", Notification, Notification.user_id.in_(user_ids or [])
    )
    await _del("appointments", Appointment, Appointment.id.in_(appt_ids or []))
    await _del(
        "patient_clinic_links", PatientClinicLink,
        or_(
            PatientClinicLink.patient_id.in_(user_ids or []),
            PatientClinicLink.clinic_id.in_(clinic_ids or []),
        ),
    )
    await _del(
        "clinic_memberships", ClinicMembership,
        or_(
            ClinicMembership.clinic_id.in_(clinic_ids or []),
            ClinicMembership.user_id.in_(user_ids or []),
        ),
    )
    await _del(
        "clinic_branches", ClinicBranch,
        ClinicBranch.clinic_id.in_(clinic_ids or []),
    )
    await _del("clinics", Clinic, Clinic.id.in_(clinic_ids or []))
    await _del("doctors", Doctor, Doctor.user_id.in_(user_ids or []))
    await _del("users", User, User.id.in_(user_ids or []))

    await db.commit()

    print("\n" + "=" * 60)
    print("DROP SUMMARY (seeded rows removed)")
    print("=" * 60)
    for entity, count in deleted.items():
        print(f"{entity:<24} deleted: {count}")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Seed (or drop) demo data for development"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Delete all rows belonging to the seeded dataset",
    )
    args = parser.parse_args()

    async with async_session() as db:
        if args.drop:
            await drop_seeded(db)
        else:
            seeder = DemoSeeder(db)
            await seeder.run()
            seeder.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
