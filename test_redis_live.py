import asyncio, redis.asyncio as aioredis, sys
sys.path.insert(0, '/app')
from services.redis_memory import get_history, save_history, session_exists, get_session_ttl, clear_history

async def test():
    r = await aioredis.from_url('redis://redis:6379', decode_responses=True)
    
    sid = 'web_unittest'
    
    # Test 1: empty history on new session
    h = await get_history(r, sid)
    print('Test 1 - New session history:', h)
    assert h == [], 'FAIL: should be empty list'
    print('Test 1 PASSED')

    # Test 2: session should not exist yet
    exists = await session_exists(r, sid)
    print('Test 2 - Session exists before save:', exists)
    assert exists == False, 'FAIL: should not exist'
    print('Test 2 PASSED')

    # Test 3: save and retrieve
    msgs = [
        {'role': 'user',      'content': 'Book me a doctor'},
        {'role': 'assistant', 'content': 'Which specialty?'},
        {'role': 'user',      'content': 'Cardiology please'},
    ]
    await save_history(r, sid, msgs)
    h2 = await get_history(r, sid)
    print('Test 3 - After save, turns retrieved:', len(h2))
    assert len(h2) == 3, 'FAIL: should have 3 turns'
    assert h2[0]['content'] == 'Book me a doctor', 'FAIL: content mismatch'
    print('Test 3 PASSED')

    # Test 4: session exists after save
    exists2 = await session_exists(r, sid)
    print('Test 4 - Session exists after save:', exists2)
    assert exists2 == True, 'FAIL: should exist'
    print('Test 4 PASSED')

    # Test 5: TTL is set correctly (~1800 seconds)
    ttl = await get_session_ttl(r, sid)
    print('Test 5 - TTL remaining:', ttl, 'seconds')
    assert ttl is not None and ttl > 1790, 'FAIL: TTL should be ~1800'
    print('Test 5 PASSED')

    # Test 6: only keeps last 8 turns (trim logic)
    big = [{'role': 'user', 'content': f'msg {i}'} for i in range(12)]
    await save_history(r, sid, big)
    h3 = await get_history(r, sid)
    print('Test 6 - After 12 msgs, stored turns:', len(h3))
    assert len(h3) == 8, 'FAIL: should trim to 8'
    assert h3[0]['content'] == 'msg 4', 'FAIL: should keep LAST 8'
    print('Test 6 PASSED')

    # Test 7: clear session
    await clear_history(r, sid)
    h4 = await get_history(r, sid)
    print('Test 7 - After clear, history:', h4)
    assert h4 == [], 'FAIL: should be empty after clear'
    print('Test 7 PASSED')

    # Test 8: TTL expiry simulation (3 second TTL)
    import json
    await r.setex('session:expiry_test:history', 3, json.dumps([{'role':'user','content':'hello'}]))
    print('Test 8 - Saved with 3s TTL...')
    import time; time.sleep(4)
    raw = await r.get('session:expiry_test:history')
    h5 = await get_history(r, 'expiry_test')
    print('Test 8 - After expiry, get_history returns:', h5)
    assert h5 == [], 'FAIL: should return empty list after TTL expiry'
    print('Test 8 PASSED')

    await r.aclose()
    print()
    print('ALL 8 TESTS PASSED - Redis implementation is correct')

asyncio.run(test())
