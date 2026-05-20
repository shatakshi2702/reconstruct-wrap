import httpx
import asyncio
import json

async def test_fullstack():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Login
        login_url = "http://127.0.0.1:8000/auth/login"
        user_data = {"email": "dev@bobthebuilder.ai", "password": "dev123"}
        
        print("Logging in...")
        res = await client.post(login_url, json=user_data)
        if res.status_code != 200:
            print(f"Login failed: {res.text}")
            return
            
        token = res.json().get("access_token")
        
        print("Requesting Fullstack Generation (this may take 30s+)...")
        generate_url = "http://127.0.0.1:8000/generate/"
        payload = {
            "prompt": "A pet shop called Paws & Claws",
            "type": "fullstack"
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        try:
            res = await client.post(generate_url, json=payload, headers=headers)
        except httpx.ReadTimeout:
            print("ERROR: Timeout! The server took too long.")
            return

        if res.status_code == 200:
            data = res.json()
            output = data.get("output")
            # Output should be a dict/object
            print("Response Type:", type(output))
            if isinstance(output, dict):
                print("Keys:", output.keys())
                frontendOutput = output.get("frontend", "")
                backendOutput = output.get("backend", "")
                
                if isinstance(frontendOutput, dict):
                    print("Frontend Keys:", frontendOutput.keys())
                    print("✅ Frontend is Multi-File Object")
                    if "preview" in frontendOutput:
                        print(f"Preview Length: {len(frontendOutput['preview'])}")
                        print("✅ Frontend has Preview Bundle")
                    if "files" in frontendOutput:
                        print(f"✅ Frontend Files: {list(frontendOutput['files'].keys())}")
                else:
                    print("Frontend Length:", len(frontendOutput))
                    if "html" in frontendOutput or "React" in frontendOutput:
                         print("✅ Frontend looks like Code")
            else:
                print("❌ Output is not a dict:", output[:100])
        else:
            print(f"❌ Failed: {res.status_code} - {res.text}")

if __name__ == "__main__":
    asyncio.run(test_fullstack())
