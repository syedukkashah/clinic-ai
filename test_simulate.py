import asyncio, sys
sys.path.insert(0, '/app')
from services.redis_memory import get_history, save_history, session_exists

async def simulate_booking_agent():
    import redis.asyncio as aioredis
    r = await aioredis.from_url('redis://redis:6379', decode_responses=True)
    
    sid = 'web_demo123'
    
    # Turn 1 - patient sends first message
    history = await get_history(r, sid)
    print('Agent got history:', history)  # [] - new session
    history.append({'role': 'user', 'content': 'I need a cardiologist tomorrow'})
    history.append({'role': 'assistant', 'content': 'Morning or afternoon?'})
    await save_history(r, sid, history)
    print('Turn 1 saved')

    # Turn 2 - patient replies
    history = await get_history(r, sid)
    print('Agent remembered', len(history), 'turns')
    history.append({'role': 'user', 'content': 'Morning please'})
    history.append({'role': 'assistant', 'content': 'Confirmed! Dr. Khan at 9am'})
    await save_history(r, sid, history)
    print('Turn 2 saved')

    await r.aclose()

asyncio.run(simulate_booking_agent())
