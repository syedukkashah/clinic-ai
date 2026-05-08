# POST /api/chat — Text booking
Request:   { "message": string, "session_id": string }
Response:  { "response": string, "appointment": AppointmentObject|null, "language": "en"|"ur" }
 
# POST /api/voice/chat — Voice booking
Request:   multipart/form-data { audio: File, session_id: string }
Response:  { "transcript": string, "text_response": string, "audio_url": string,
             "detected_lang": "en"|"ur", "appointment": AppointmentObject|null }
 
# GET /api/slots?doctor_id=&date=&specialty=
Response:  { "slots": [{ "slot_id": int, "doctor_id": int, "doctor_name": string,
                          "start_time": string, "predicted_wait_minutes": float }] }
 
# POST /api/appointments — create (used internally by agent tool)
Request:   { "patient_id": int, "slot_id": int, "complaint": string }
Response:  { "appointment_id": int, "confirmed": bool, "doctor_name": string,
             "start_time": string, "predicted_wait": float }
 
# POST /predict/wait-time — ML service
Request:   { "slot_id": int, "doctor_id": int, "hour_of_day": int, ... }
Response:  { "predicted_wait_minutes": float, "model_version": string }
 
# POST /predict/patient-load — ML service
Request:   { "doctor_id": int, "date": string }
Response:  { "forecast": {"8":int,"9":int,...,"20":int},
             "peak_hour": int, "peak_hour_patients": int }
 
# AppointmentObject (shared type used in all responses):
{ "appointment_id":int, "patient_id":int, "doctor_id":int, "doctor_name":string,
  "start_time":string, "specialty":string, "predicted_wait_minutes":float,
  "status":"confirmed"|"cancelled"|"rescheduled" }