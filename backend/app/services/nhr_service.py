"""
NHR (National Health Registry) verification stub service  [MD-210]

Returns a mock verification response. Designed for future real NHR API integration.
"""
import asyncio
import uuid


async def verify_license(
    license_number: str,
    license_council: str,
    license_year: int,
    doctor_name: str,
) -> dict:
    """
    Stub NHR verification. Simulates a short async delay.
    In production, replace with actual NHR API call.

    Returns:
        dict with keys: verified (bool), notes (str), nhr_id (str|None)
    """
    # Simulate network latency
    await asyncio.sleep(0.5)

    # Stub logic: treat license_number starting with "INVALID" as failure
    if license_number.upper().startswith("INVALID"):
        return {
            "verified": False,
            "notes": "License number not found in NHR registry (stub response)",
            "nhr_id": None,
        }

    return {
        "verified": True,
        "notes": "License verified successfully via NHR (stub response)",
        "nhr_id": f"NHR-{uuid.uuid4().hex[:8].upper()}",
    }
