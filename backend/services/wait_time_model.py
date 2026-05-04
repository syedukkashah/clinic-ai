import random


def predict_wait_time(current_load: int | None = None):
    if current_load is None:
        return round(8 + random.random() * 32, 1)
    base_wait = 10
    extra_wait_per_patient = 5
    return base_wait + current_load * extra_wait_per_patient


def predict_patient_load():
    return round(15 + random.random() * 10, 0)
