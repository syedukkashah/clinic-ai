def analyze_symptoms(symptoms: str) -> dict:
    text = symptoms.lower()

    if "chest pain" in text or "difficulty breathing" in text:
        return {
            "urgency": "high",
            "specialty": "emergency"
        }

    if "headache" in text:
        return {
            "urgency": "medium",
            "specialty": "general physician"
        }

    if "fever" in text or "cough" in text:
        return {
            "urgency": "medium",
            "specialty": "general physician"
        }

    return {
        "urgency": "low",
        "specialty": "general physician"
    }