import asyncio
import pandas as pd
from httpx import AsyncClient, ASGITransport
from main import app

async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/predict/patient-load",
            json={"doctor_id": 1, "date": "2020-01-01", "specialty": "general"}
        )
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")

if __name__ == "__main__":
    asyncio.run(test())
