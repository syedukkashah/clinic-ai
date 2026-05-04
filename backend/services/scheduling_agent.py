from sqlalchemy.orm import Session
from backend.db.models import Appointment, Doctor, Notification, OpsAlert
from backend.services.ml_service import ml_service_client
from backend.core.logging import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)

OVERLOAD_THRESHOLD_MINUTES = 45
PREFERRED_WAIT_TIME_MINUTES = 20

async def run_proactive_scheduling(db: Session):
    """
    Main function for the proactive scheduling agent.
    - Fetches upcoming appointments.
    - Checks for doctor overload using ML predictions.
    - Reassigns appointments if necessary to reduce wait times.
    """
    logger.info("Starting proactive scheduling run...")
    
    # 1. Get next 4 hours of appointments
    now = datetime.utcnow()
    four_hours_later = now + timedelta(hours=4)
    
    upcoming_appointments = db.query(Appointment).filter(
        Appointment.start_time >= now,
        Appointment.start_time <= four_hours_later,
        Appointment.status == 'confirmed'
    ).all()

    if not upcoming_appointments:
        logger.info("No upcoming appointments to process.")
        return {"status": "No appointments to process"}

    # Group appointments by doctor
    appointments_by_doctor = {}
    for appt in upcoming_appointments:
        if appt.doctor_id not in appointments_by_doctor:
            appointments_by_doctor[appt.doctor_id] = []
        appointments_by_doctor[appt.doctor_id].append(appt)

    reassignments = 0
    overloads_detected = 0

    # 2. For each doctor, check load and wait times
    for doctor_id, appointments in appointments_by_doctor.items():
        doctor = db.query(Doctor).get(doctor_id)
        if not doctor:
            continue

        # Call patient-load model
        patient_load_payload = {
            "doctor_id": doctor.id,
            "date": now.strftime("%Y-%m-%d")
        }
        patient_load_forecast = await ml_service_client.get_patient_load(patient_load_payload)

        if "error" in patient_load_forecast:
            logger.error(f"Could not get patient load for Dr. {doctor.name}. Skipping.")
            continue

        # Simple overload check: if peak hour patients > threshold (e.g., 8)
        if patient_load_forecast.get("peak_hour_patients", 0) > 8:
            overloads_detected += 1
            logger.warning(f"Overload detected for Dr. {doctor.name}. Peak patients: {patient_load_forecast['peak_hour_patients']}")
            
            # Check wait times for this doctor's appointments
            for appt in appointments:
                wait_time_payload = {
                    "slot_id": appt.id,
                    "doctor_id": doctor.id,
                    "hour_of_day": appt.start_time.hour,
                    "day_of_week": appt.start_time.weekday(),
                    "queue_depth": len(appointments), # Simplified queue depth
                    "specialty": doctor.specialty
                }
                wait_time_prediction = await ml_service_client.get_wait_time(wait_time_payload)

                if "error" in wait_time_prediction:
                    logger.error(f"Could not get wait time for appt {appt.id}. Skipping.")
                    continue

                predicted_wait = wait_time_prediction.get("predicted_wait_minutes", 0)
                
                if predicted_wait > OVERLOAD_THRESHOLD_MINUTES:
                    logger.info(f"High wait time ({predicted_wait} min) for appt {appt.id}. Finding alternative.")
                    
                    # 3. Find and evaluate alternative slots
                    new_slot = await find_and_evaluate_alternative(db, appt, doctor)
                    
                    if new_slot:
                        # 4. Reassign appointment and notify
                        original_start_time = appt.start_time
                        appt.start_time = new_slot.start_time
                        appt.end_time = new_slot.end_time
                        appt.doctor_id = new_slot.doctor_id # In case we switch doctors
                        db.commit()
                        reassignments += 1
                        
                        # Create notification for patient
                        create_patient_notification(db, appt, original_start_time)
                        
                        # Create alert for operations
                        create_ops_alert(db, appt, doctor, original_start_time, predicted_wait)
                        
                        logger.info(f"Successfully reassigned appointment {appt.id} to {new_slot.start_time}")

    logger.info(f"Scheduling run finished. Overloads detected: {overloads_detected}, Appointments reassigned: {reassignments}.")
    return {"overloads_detected": overloads_detected, "appointments_reassigned": reassignments}


async def find_and_evaluate_alternative(db: Session, current_appt: Appointment, doctor: Doctor):
    """
    Finds a better slot for an appointment.
    """
    # Simplified logic: Look for an open slot in the next 8 hours
    search_start = current_appt.start_time + timedelta(minutes=30)
    search_end = search_start + timedelta(hours=8)

    # This is a placeholder for a more complex slot-finding logic.
    # In a real system, you'd query for available `Slot` records.
    # For now, we'll simulate finding a slot 2 hours later.
    
    potential_new_start = current_appt.start_time + timedelta(hours=2)
    
    # Mock a "found" slot for demonstration
    class MockSlot:
        def __init__(self, start, end, doc_id):
            self.start_time = start
            self.end_time = end
            self.doctor_id = doc_id

    new_slot_time = MockSlot(potential_new_start, potential_new_start + timedelta(minutes=30), doctor.id)

    # Call wait-time model for the new slot
    new_wait_time_payload = {
        "slot_id": current_appt.id, # Still same appointment
        "doctor_id": new_slot_time.doctor_id,
        "hour_of_day": new_slot_time.start_time.hour,
        "day_of_week": new_slot_time.start_time.weekday(),
        "queue_depth": 2, # Simplified: assume lower queue
        "specialty": doctor.specialty
    }
    new_wait_prediction = await ml_service_client.get_wait_time(new_wait_time_payload)

    if "error" in new_wait_prediction:
        logger.error("Could not evaluate alternative slot.")
        return None

    new_predicted_wait = new_wait_prediction.get("predicted_wait_minutes", 100)

    if new_predicted_wait < PREFERRED_WAIT_TIME_MINUTES:
        logger.info(f"Found suitable alternative slot with wait time: {new_predicted_wait} min.")
        return new_slot_time
    
    logger.info("No suitable alternative slot found.")
    return None

def create_patient_notification(db: Session, appointment: Appointment, original_start_time: datetime):
    """Creates a notification for the patient about the schedule change."""
    message = (
        f"Your appointment with Dr. {appointment.doctor.name} on "
        f"{original_start_time.strftime('%B %d')} has been moved from "
        f"{original_start_time.strftime('%I:%M %p')} to "
        f"{appointment.start_time.strftime('%I:%M %p')} to ensure a shorter wait time."
    )
    notification = Notification(
        patient_id=appointment.patient_id,
        message=message,
        status='pending'
    )
    db.add(notification)
    db.commit()
    logger.info(f"Created patient notification for appointment {appointment.id}")

def create_ops_alert(db: Session, appointment: Appointment, original_doctor: Doctor, original_start_time: datetime, original_wait: float):
    """Creates an operational alert for internal monitoring."""
    message = (
        f"Auto-reschedule due to overload for Dr. {original_doctor.name}. "
        f"Appt #{appointment.id} moved from {original_start_time.strftime('%I:%M %p')} "
        f"to {appointment.start_time.strftime('%I:%M %p')} with Dr. {appointment.doctor.name}."
    )
    details = {
        "original_doctor_id": original_doctor.id,
        "new_doctor_id": appointment.doctor_id,
        "appointment_id": appointment.id,
        "original_start_time": original_start_time.isoformat(),
        "new_start_time": appointment.start_time.isoformat(),
        "original_predicted_wait": original_wait,
        "trigger": "proactive_scheduling_agent"
    }
    alert = OpsAlert(
        message=message,
        severity='warning',
        details=details
    )
    db.add(alert)
    db.commit()
    logger.info(f"Created ops alert for appointment {appointment.id}")
