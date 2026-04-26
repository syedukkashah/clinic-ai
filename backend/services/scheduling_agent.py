def assign_doctor(specialty: str, preferred_time: str, doctors: list[dict]) -> dict:
    matching_doctors = [
        doctor for doctor in doctors
        if doctor["specialty"] == specialty and preferred_time in doctor["available_times"]
    ]

    if not matching_doctors:
        return {"error": "No doctor available for that specialty and time"}

    best_doctor = min(matching_doctors, key=lambda doctor: doctor["current_load"])
    return best_doctor