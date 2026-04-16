import asyncio
import time
from app.services.db import init_db, _get_ingestion_status_sync, get_ingestion_status

init_db()

async def baseline():
    start = time.time()
    for _ in range(1000):
        _get_ingestion_status_sync()
    end = time.time()
    return end - start

async def async_optimized():
    start = time.time()
    for _ in range(1000):
        await get_ingestion_status()
    end = time.time()
    return end - start

async def main():
    print(f"Sync (blocking): {await baseline():.4f}s")
    print(f"Async (optimized): {await async_optimized():.4f}s")

if __name__ == "__main__":
    asyncio.run(main())
