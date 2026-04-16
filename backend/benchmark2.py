import asyncio
import time
from app.services.db import init_db, _get_ingestion_status_sync, get_ingestion_status

init_db()

async def block_task():
    for _ in range(100):
        _get_ingestion_status_sync()

async def non_block_task():
    for _ in range(100):
        await get_ingestion_status()

async def measure_latency(task_func):
    start = time.time()

    async def ticker():
        ticks = 0
        while time.time() - start < 0.5:
            await asyncio.sleep(0.01)
            ticks += 1
        return ticks

    task1 = asyncio.create_task(ticker())
    task2 = asyncio.create_task(task_func())

    ticks = await task1
    await task2
    return ticks

async def main():
    ticks_block = await measure_latency(block_task)
    print(f"Ticks with blocking DB: {ticks_block}")
    ticks_nonblock = await measure_latency(non_block_task)
    print(f"Ticks with non-blocking DB: {ticks_nonblock}")

if __name__ == "__main__":
    asyncio.run(main())
