import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_expense_crud():

    async with AsyncClient(app=app, base_url="http://test") as ac:

        # Login
        login = await ac.post("/auth/login", json={
            "email": "testuser@test.com",
            "password": "Test12345"
        })

        token = login.json()["access_token"]

        headers = {
            "Authorization": f"Bearer {token}"
        }

        # Create
        res = await ac.post("/expenses/", json={
            "amount": 100,
            "category": "food",
            "description": "test"
        }, headers=headers)

        assert res.status_code == 201

        expense_id = res.json()["id"]

        # List
        res = await ac.get("/expenses/", headers=headers)
        assert res.status_code == 200

        # Update
        res = await ac.put(f"/expenses/{expense_id}", json={
            "amount": 200
        }, headers=headers)

        assert res.status_code == 200

        # Delete
        res = await ac.delete(f"/expenses/{expense_id}", headers=headers)
        assert res.status_code == 204
