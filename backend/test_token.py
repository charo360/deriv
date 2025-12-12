import asyncio
import websockets
import json

async def test_token(token):
    uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    async with websockets.connect(uri) as ws:
        # Authorize
        await ws.send(json.dumps({"authorize": token, "req_id": 1}))
        response = await ws.recv()
        print("Auth response:")
        print(json.dumps(json.loads(response), indent=2)[:500])
        
        # Subscribe to ticks
        await ws.send(json.dumps({"ticks": "R_75", "subscribe": 1, "req_id": 2}))
        response = await ws.recv()
        print("\nTicks response:")
        data = json.loads(response)
        print(f"msg_type: {data.get('msg_type')}, req_id: {data.get('req_id')} (type: {type(data.get('req_id'))})")
        
        # Subscribe to candles
        await ws.send(json.dumps({
            "ticks_history": "R_75",
            "adjust_start_time": 1,
            "count": 10,
            "end": "latest",
            "granularity": 60,
            "style": "candles",
            "subscribe": 1,
            "req_id": 3
        }))
        response = await ws.recv()
        print("\nCandles response:")
        data = json.loads(response)
        print(f"msg_type: {data.get('msg_type')}, req_id: {data.get('req_id')} (type: {type(data.get('req_id'))})")
        print(f"Keys: {list(data.keys())}")

if __name__ == "__main__":
    token = "yIeFvovfvnqwyVj"
    asyncio.run(test_token(token))
