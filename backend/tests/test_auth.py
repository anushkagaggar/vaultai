import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_register_and_login():

    async with AsyncClient(app=app, base_url="http://test") as ac:

        # Register
        res = await ac.post("/auth/register", json={
            "email": "testuser@test.com",
            "password": "Test12345"
        })

        assert res.status_code in (200, 201, 400)

        # Login
        res = await ac.post("/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test12345"
        })

        assert res.status_code == 200
        assert "access_token" in res.json()
