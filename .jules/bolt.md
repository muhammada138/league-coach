## 2026-04-19 - Avoid synchronous SQLite queries in async loops
**Learning:** Using synchronous SQLite database queries inside async loops (such as `db._get_ingestion_status_sync()`) blocks the async event loop and causes N+1 performance bottlenecks.
**Action:** Always use the async wrapped version (e.g., `await db.get_ingestion_status()`) inside async functions and loops to maintain event loop responsiveness.
