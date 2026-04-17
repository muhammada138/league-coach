import asyncio
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run():
    response = client.get("/analyze/fake-puuid?game_name=Faker&count=5")
    print(response.status_code)
    print(response.text)

if __name__ == "__main__":
    run()
