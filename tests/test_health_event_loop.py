import asyncio
from threading import Event

import httpx
from fastapi import FastAPI


def test_system_health_allows_readiness_callback_on_same_event_loop(monkeypatch):
    """Molt readiness can call app liveness while app collects system health."""
    from app.dashboard.api import system

    collecting = Event()
    callback_received = Event()

    def collector():
        collecting.set()
        ready = callback_received.wait(timeout=3)
        return {"status": "ok" if ready else "warn"}

    monkeypatch.setattr(system, "collect_system_health", collector)
    app = FastAPI()
    app.include_router(system.router)

    @app.get("/health")
    async def liveness():
        callback_received.set()
        return {"status": "ok"}

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            checking = asyncio.create_task(client.get("/system/health"))
            assert await asyncio.to_thread(collecting.wait, 3)
            assert (await client.get("/health")).status_code == 200
            response = await checking
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    asyncio.run(exercise())
