# Performance Learnings

## In-Memory Caching with Modification Time Validation
In performance-critical paths (like win prediction) that depend on external JSON metadata, reading and parsing the file on every request blocks the asynchronous event loop, significantly degrading throughput.

### Problem
Synchronous `json.load()` for a ~1MB file takes approximately 10ms. In a high-concurrency FastAPI environment, this blocks the main thread and limits the application to ~100 requests per second per worker, even if other operations are asynchronous.

### Solution
Implement an in-memory cache validated by the file's modification time (`os.path.getmtime`). This reduces the overhead per call to ~8 microseconds (a ~99% improvement) while ensuring data consistency when the underlying file is updated by background processes (like the `meta_scraper` sync).

### Implementation Pattern
```python
_CACHE = None
_LAST_MOD = 0

def get_data():
    global _CACHE, _LAST_MOD
    mtime = os.path.getmtime(FILE_PATH)
    if _CACHE is not None and mtime <= _LAST_MOD:
        return _CACHE

    with open(FILE_PATH, "r") as f:
        data = json.load(f)
        _CACHE = data
        _LAST_MOD = mtime
        return data

def save_data(data):
    # write to file...
    # update cache immediately
    global _CACHE, _LAST_MOD
    _CACHE = data
    _LAST_MOD = os.path.getmtime(FILE_PATH)
```
