import time
import asyncio
from functools import partial
from groq import Groq
from app.config import settings
import re
import json

def extract_code_block(text: str) -> str:
    """Extracts content from markdown code blocks or returns raw text."""
    pattern = r"```(?:html|javascript|js|jsx|python|py|json)?\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

# Synchronous Groq client (SDK is sync-only)
client = Groq(api_key=settings.GROQ_API_KEY)


def _sync_call(model: str, messages: list, temperature: float = 0.7,
               max_tokens: int = 8192, response_format: dict | None = None) -> str:
    """Run a synchronous Groq API call and return the content string."""
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if response_format:
        kwargs["response_format"] = response_format
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content


async def _async_call(model: str, messages: list, temperature: float = 0.7,
                      max_tokens: int = 8192, response_format: dict | None = None) -> str:
    """Run a sync Groq call in a thread executor so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    fn = partial(_sync_call, model, messages, temperature, max_tokens, response_format)
    return await loop.run_in_executor(None, fn)


# ─── Public Generation Functions ───

async def generate_text(prompt: str):
    start = time.time()
    content = await _async_call(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
    )
    return content, int((time.time() - start) * 1000)


async def generate_website(prompt: str):
    start = time.time()

    system_prompt = """You are a World-Class Senior Frontend Engineer and UI/UX Designer.
Your goal is to build an "Awwwards-Winning" landing page that looks expensive, premium, and trustworthy.

### 1. DESIGN SYSTEM (Tailwind CSS)
- **Typography**: `font-sans` (Inter/Plus Jakarta Sans).
- **Colors**: Use a refined palette.
  - Primary: `indigo-600` to `violet-600` (gradients).
  - Background: `slate-900` (Dark Mode) or `slate-50` (Light Mode).
  - Text: `slate-100` or `slate-900`.
- **Effects**:
  - Glassmorphism: `bg-white/10 backdrop-blur-lg border border-white/20`.
  - Shadows: `shadow-2xl shadow-indigo-500/20`.
  - Gradients: `bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500`.

### 2. COMPOSITION (Sections)
You MUST include these sections in order:
1. **Navbar**: Sticky, glassmorphism, Logo (text is fine), Navigation Links, CTA Button.
2. **Hero Section**: Huge headline, subheadline, 2 buttons (Primary/Secondary), and a **Large AI Hero Image**.
3. **Logos Cloud**: "Trusted by" section with opacity-50 logos (use FontAwesome icons as fake logos).
4. **Features Grid**: Bento-grid style or 3-column layout. Cards with icons and descriptions.
5. **How It Works**: Step-by-step process with connecting lines or numbers.
6. **Testimonials**: Masonry layout or grid of glowing reviews.
7. **Pricing**: 3 Cards (Basic, Pro, Enterprise). Highlight "Pro".
8. **FAQ**: Accordion style (using `<details>` and `<summary>` for simplicity).
9. **Footer**: Links, Newsletter input, Social icons.

### 3. CRITICAL: IMAGES (Pollinations AI)
- **Hero Image**: `https://image.pollinations.ai/prompt/{contextual_hero_description}?nologo=true`
- **Feature Icons**: Use FontAwesome OR `https://image.pollinations.ai/prompt/icon_{feature_name}?nologo=true`
- **Backgrounds**: Use subtle abstract backgrounds.
- **Descriptions**: MUST be specific to the user's prompt (e.g., "chef cooking" for food app).

### 4. INTERACTIVITY
- **Hover**: `hover:-translate-y-2 hover:shadow-xl transition-all duration-300`.
- **Animations**: Add `group` classes for hover effects.

### OUTPUT FORMAT
- Return ONLY valid HTML5 code.
- Include `<script src="https://cdn.tailwindcss.com"></script>`.
- Include `<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">`.
- Include Google Fonts link.
"""

    content = await _async_call(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Build a premium, high-converting website for: {prompt}. Ensure it feels like a $50k/year startup product."}
        ],
        temperature=0.7,
        max_tokens=8192,
    )

    output = extract_code_block(content)
    return output, int((time.time() - start) * 1000)


async def generate_backend_code(prompt: str):
    start = time.time()

    system_prompt = """You are a Principal Software Architect.
Your task is to generate a comprehensive **FastAPI Backend Project** with multiple files.
You MUST return a valid JSON object where keys are file paths and values are the code content.

### PROJECT STRUCTURE
1. `requirements.txt`: List dependencies (fastapi, uvicorn, sqlalchemy, pydantic, python-jose[cryptography], passlib[bcrypt], multipart).
2. `app/database.py`: SQLAlchemy setup (Base, engine, SessionLocal, get_db).
3. `app/models.py`: SQLAlchemy models (User, and domain specific models).
4. `app/schemas.py`: Pydantic schemas (UserCreate, Token, domain schemas).
5. `app/auth.py`: JWT logic, login endpoint, register endpoint, get_current_user dependency.
6. `app/main.py`: App initialization, include routers, CORS setup (allow *).

### REQUIREMENTS
- **Database**: `sqlite:///./app.db`.
- **Auth**: Implement full JWT auth flow.
- **Business Logic**: Implement CRUD for the user's requested domain in `main.py` (or a separate router file if you prefer).
- **Seeding**: In `main.py`, add `@app.on_event("startup")` to create initial data if tables are empty.

### OUTPUT FORMAT
- Return ONLY the raw JSON string. Do not include markdown formatting like ```json ... ```.
- Example:
{
  "requirements.txt": "fastapi...",
  "app/main.py": "from fastapi import..."
}
"""

    content = await _async_call(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a multi-file FastAPI project for: {prompt}. Return JSON only."}
        ],
        temperature=0.5,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    json_str = extract_code_block(content)
    try:
        project_dict = json.loads(json_str)
        return project_dict, int((time.time() - start) * 1000)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw": content}, int((time.time() - start) * 1000)


async def generate_functional_frontend(prompt: str):
    start = time.time()

    system_prompt = """You are a Senior Frontend Architect.
Your task is to generate a **Complex, Production-Grade React Application**.

### OUTPUT FORMAT: JSON
Return a JSON object with TWO keys:
1. `files`: A dictionary of file paths and code (Standard React Project structure).
   - Must include: `src/App.jsx`, `src/main.jsx`, `src/components/...` (Sidebar, Navbar, Cards), `src/pages/...` (Dashboard, Login, Settings).
   - Use `import` and `export` syntax.
   - Separate concerns (logic, UI, data fetching).
   - Use `axios` for API calls to `http://localhost:8000`.
   - Use **Tailwind CSS** for styling (glassmorphism, premium feel, dark mode).
2. `preview`: A SINGLE STRING containing the ENTIRE application for a Live Demo.
   - **NO** `import` or `export` statements.
   - Concatenate all components (App, Sidebar, Pages) into this one string so it can run in a browser script tag.
   - End with `const root = ReactDOM.createRoot(document.getElementById('root')); root.render(<ErrorBoundary><App /></ErrorBoundary>);`.

### REQUIREMENTS
- **Complexity**: Multiple pages (Dashboard, Settings, User Profile), complex UI components (DataTables, Modal, Forms).
- **Data**: Fetch real data from backend, fallback to mock data if failed.
- **Styling**: Premium, polished UI.

### EXAMPLE JSON Structure
{
  "files": {
    "src/App.jsx": "import React from 'react';...",
    "src/components/Header.jsx": "export default function Header()..."
  },
  "preview": "const Header = () => <div>...</div>; const App = () => <Header />; const root = ..."
}
"""

    content = await _async_call(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Build a complex React app for: {prompt}. Connect to localhost:8000. Return JSON."}
        ],
        temperature=0.7,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    json_str = extract_code_block(content)
    try:
        data = json.loads(json_str)
        return data, int((time.time() - start) * 1000)
    except Exception:
        return {"preview": "// Failed to generate complex structure. Please try again.", "files": {}}, int((time.time() - start) * 1000)


async def generate_fullstack(prompt: str):
    start = time.time()
    # Run both in parallel since they are now truly async (thread executor)
    frontend_task = generate_functional_frontend(prompt)
    backend_task = generate_backend_code(prompt)

    (frontend_code, _), (backend_code, _) = await asyncio.gather(frontend_task, backend_task)

    return {
        "frontend": frontend_code,
        "backend": backend_code
    }, int((time.time() - start) * 1000)


async def refine_website(current_code: str, prompt: str):
    start = time.time()

    system_prompt = """You are an expert AI Web Developer.
Edit the provided HTML based on the request.
Maintain Tailwind CSS and Pollinations.ai images.
Return ONLY raw HTML.
"""

    user_message = f"""
HTML:
{current_code}

Request: {prompt}
"""

    content = await _async_call(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.7,
        max_tokens=8192,
    )

    output = extract_code_block(content)
    return output, int((time.time() - start) * 1000)
