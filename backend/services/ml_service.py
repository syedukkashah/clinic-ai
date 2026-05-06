import httpx
import os
from typing import Dict, Any
from core.logging import get_logger

logger = get_logger(__name__)

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8001")

class MLServiceClient:
    def __init__(self, base_url: str = ML_SERVICE_URL):
        self.base_url = base_url

    async def get_wait_time(self, slot_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls the ML service to predict wait time for a given slot.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/predict/wait-time", json=slot_data, timeout=5.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error calling wait-time prediction: {e.response.status_code} {e.response.text}")
                return {"error": "Failed to get wait time prediction", "details": str(e)}
            except httpx.RequestError as e:
                logger.error(f"Request error calling wait-time prediction: {e}")
                return {"error": "Request to ML service failed", "details": str(e)}

    async def get_patient_load(self, load_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls the ML service to forecast patient load for a doctor.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/predict/patient-load", json=load_data, timeout=5.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error calling patient-load prediction: {e.response.status_code} {e.response.text}")
                return {"error": "Failed to get patient load forecast", "details": str(e)}
            except httpx.RequestError as e:
                logger.error(f"Request error calling patient-load prediction: {e}")
                return {"error": "Request to ML service failed", "details": str(e)}

ml_service_client = MLServiceClient()
