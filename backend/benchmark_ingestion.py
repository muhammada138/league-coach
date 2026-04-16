import time
from app.services import db

def run_benchmark():
    db.init_db()

    # 1. Benchmark calling _get_ingestion_status_sync() inside a loop of size 10
    start = time.perf_counter()
    for _ in range(1000):
        for _ in range(10):
            status = db._get_ingestion_status_sync()
    end = time.perf_counter()
    print(f"10 iterations in loop x 1000: {end - start:.4f}s")

    # 2. Benchmark hoisting _get_ingestion_status_sync()
    start = time.perf_counter()
    for _ in range(1000):
        status = db._get_ingestion_status_sync()
        for _ in range(10):
            pass
    end = time.perf_counter()
    print(f"Hoisted x 1000: {end - start:.4f}s")

if __name__ == "__main__":
    run_benchmark()
