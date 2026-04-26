def predict_wait_time(current_load: int) -> int:
    base_wait = 10
    extra_wait_per_patient = 5
    return base_wait + current_load * extra_wait_per_patient