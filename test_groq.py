from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    print("Testing DeepSeek on Groq...")
    completion = client.chat.completions.create(
        model="deepseek-r1-distill-llama-70b",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("Success:", completion.choices[0].message.content)
except Exception as e:
    print("Error:", e)
