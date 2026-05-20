import httpx
import asyncio

async def test_backend_gen():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Login
        login_url = "http://127.0.0.1:8000/auth/login"
        user_data = {"email": "startup_test@example.com", "password": "password123"}
        await client.post("http://127.0.0.1:8000/auth/register", json=user_data) # Ensure user
        
        res = await client.post(login_url, json=user_data)
        token = res.json().get("access_token")
        
        if not token:
            print("Login failed")
            return

        print("Generating Backend...")
        res = await client.post(
            "http://127.0.0.1:8000/generate/", 
            json={"prompt": "A todo list API with CRUD", "type": "backend"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if res.status_code == 200:
            output = res.json().get("output", "")
            print("Success! Output length:", len(output))
            if "FastAPI" in output or "fastapi" in output:
                print("FastAPI detected.")
            else:
                print("Warning: FastAPI not detected.")
                
            with open("generated_backend.py", "w") as f:
                f.write(output)
        else:
            print("Failed:", res.text)

if __name__ == "__main__":
    asyncio.run(test_backend_gen())
