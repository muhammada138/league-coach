import pytest
from app.services.ingestion import _rank_cache

@pytest.fixture(autouse=True)
def clear_rank_cache():
    _rank_cache.clear()
