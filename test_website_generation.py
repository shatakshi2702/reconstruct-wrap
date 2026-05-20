import httpx
import asyncio
import random
import string

def get_random_string(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

async def test_generate_website():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login to get a token
        login_url = "http://127.0.0.1:8000/auth/login"
        register_url = "http://127.0.0.1:8000/auth/register"
        
        # Create a unique user for this test run
        random_suffix = get_random_string(8)
        email = f"test_{random_suffix}@example.com"
        password = "password123"
        user_data = {
            "email": email,
            "password": password
        }
        
        print(f"Attempting to register new test user: {email}...")
        try:
            reg_response = await client.post(register_url, json=user_data)
            if reg_response.status_code == 200:
                print("Registration successful.")
            elif reg_response.status_code == 400: # Assuming 400 for existing user
                print("User likely already exists.")
            else:
                print(f"Registration status: {reg_response.status_code}")
        except Exception as e:
             print(f"Registration failed: {e}")

        print("Attempting to login...")
        login_response = await client.post(login_url, json=user_data)
        
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            return

        token = login_response.json().get("access_token") # Assuming response structure
        if not token:
             # Check if it returns just the token or a dict
             try:
                 token_data = login_response.json()
                 if isinstance(token_data, str):
                     token = token_data
                 elif "token" in token_data:
                     token = token_data["token"]
             except:
                 pass
        
        if not token:
            print(f"Could not extract token from: {login_response.text}")
            return
            
        print("Login successful. Token received.")

        # 2. Call generate endpoint
        headers = {"Authorization": f"Bearer {token}"}
        generate_url = "http://127.0.0.1:8000/generate/"
        payload = {
            "prompt": "Create a simple portfolio website for a developer named Alex. Include a hero section with 'Hello, I'm Alex' and an about section.",
            "type": "website"
        }
        
        print(f"Testing generation with prompt: '{payload['prompt']}'...")
        try:
            # Increased timeout for generation
            gen_response = await client.post(generate_url, json=payload, headers=headers, timeout=60.0)
            
            if gen_response.status_code == 200:
                data = gen_response.json()
                output_html = data.get("output", "")
                
                if output_html:
                    filename = "test_output.html"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(output_html)
                    print(f"SUCCESS! Website generated and saved to {filename}")
                    print(f"Response time: {data.get('response_time_ms')}ms")
                    print("First 100 chars of HTML:", output_html[:100])
                else:
                    print("Generation returned 200 but no output found.")
            else:
                print(f"Generation failed with status {gen_response.status_code}: {gen_response.text}")
        except httpx.ReadTimeout:
             print("Generation timed out.")
        except Exception as e:
            print(f"An error occurred during generation: {e}")

if __name__ == "__main__":
    asyncio.run(test_generate_website())
