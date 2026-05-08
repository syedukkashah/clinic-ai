import asyncio
import os
from agents.booking_agent import process_chat_message
from db.session import AsyncSessionLocal
from redis import asyncio as aioredis

async def main():
    # Setup minimal env for local test
    os.environ["DATABASE_URL"] = "postgresql+psycopg2://mediflow:mediflow123@postgres:5432/mediflow"
    os.environ["REDIS_URL"] = "redis://redis:6379"
    
    redis = await aioredis.from_url(os.environ["REDIS_URL"])
    
    print("Testing BookingAgent...")
    try:
        response = await process_chat_message(
            user_id="test_user",
            message="Hi, what are the clinic hours?",
            redis_client=redis
        )
        print("\nAgent Response:")
        print(response)
    except Exception as e:
        print(f"\nError occurred: {e}")
    finally:
        await redis.close()

if __name__ == "__main__":
    asyncio.run(main())
