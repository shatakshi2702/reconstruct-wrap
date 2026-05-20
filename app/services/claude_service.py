"""
claude_service.py
Real-time streaming generation.
Primary: Anthropic Claude (if key set AND account has credits)
Fallback: Groq Llama 3 (chunked streaming via executor)
"""
import asyncio
import time
import re
from typing import AsyncGenerator
from functools import partial
from app.config import settings

# ─── Lazy clients ─────────────────────────────────────────────────────────────

def _get_anthropic():
    if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY.startswith("your-"):
        return None
    try:
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception:
        return None


def _get_groq():
    try:
        from groq import Groq
        return Groq(api_key=settings.GROQ_API_KEY)
    except Exception:
        return None


# ─── Prompts ──────────────────────────────────────────────────────────────────

WEBSITE_SYSTEM = """You are a World-Class Senior Frontend Engineer and UI/UX Designer.
Build an "Awwwards-Winning" landing page that looks premium, expensive, and developer-trustworthy.

DESIGN SYSTEM (Tailwind CSS via CDN):
- Typography: Inter / Plus Jakarta Sans from Google Fonts.
- Colors: indigo-600→violet-600 gradients for primary; slate-900 bg; slate-100 text.
- Effects: glassmorphism (bg-white/10 backdrop-blur-lg border border-white/20), deep shadows, gradients.

REQUIRED SECTIONS (in order):
1. Sticky glassmorphism Navbar — logo, nav links, CTA button.
2. Hero — large headline, sub-headline, two CTA buttons, Pollinations.ai hero image.
3. "Trusted by" logos cloud (FontAwesome brand icons, opacity-50).
4. Features Bento grid (3-col) — icon + title + description.
5. How It Works — numbered steps with connectors.
6. Testimonials — masonry grid with glowing cards.
7. Pricing — 3 cards (Starter/Pro/Enterprise), Pro highlighted.
8. FAQ — <details>/<summary> accordion.
9. Footer — links, newsletter input, social icons.

IMAGES — Pollinations AI:
Hero: https://image.pollinations.ai/prompt/{contextual_scene_for_prompt}?width=1200&height=600&nologo=true
Features: https://image.pollinations.ai/prompt/icon_{feature}_minimalist?width=80&height=80&nologo=true

INTERACTIVITY: hover:-translate-y-2 hover:shadow-xl transition-all duration-300 on cards.

OUTPUT — ONLY raw valid HTML5. No markdown fences. No explanations.
Include: <script src="https://cdn.tailwindcss.com"></script>
Include: <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
Include: Google Fonts <link> for Inter."""

REFINE_SYSTEM = """You are an expert AI Web Developer.
Edit ONLY what the user asks — preserve all other sections, Tailwind classes, Pollinations images.
Return ONLY the complete updated raw HTML. No markdown, no explanation."""


# ─── Groq streaming fallback (sync SDK → chunked async) ──────────────────────

async def _groq_stream(system: str, user: str) -> AsyncGenerator[str, None]:
    """Run Groq synchronously in executor and yield chunks."""
    loop = asyncio.get_event_loop()

    def _call():
        client = _get_groq()
        if not client:
            return None
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.7,
            max_tokens=8192,
        )

    completion = await loop.run_in_executor(None, _call)
    if not completion:
        yield "<!-- Groq unavailable -->"
        return

    text = completion.choices[0].message.content or ""
    # Emit in realistic chunks so the streaming UI feels live
    chunk_size = 40
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]
        await asyncio.sleep(0.008)   # tiny delay per chunk for visual effect


# ─── Claude streaming (primary) ───────────────────────────────────────────────

async def _claude_stream(system: str, user: str) -> AsyncGenerator[str, None]:
    client = _get_anthropic()
    if not client:
        async for chunk in _groq_stream(system, user):
            yield chunk
        return

    try:
        async with client.messages.stream(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": user}]
        ) as stream:
            async for text in stream.text_stream:
                yield text
    except Exception as e:
        err_lower = str(e).lower()
        if "credit" in err_lower or "billing" in err_lower or "balance" in err_lower:
            # Account has no credits — fall back to Groq silently
            print(f"[claude_service] Claude billing error, falling back to Groq: {e}")
            async for chunk in _groq_stream(system, user):
                yield chunk
        else:
            raise


# ─── Public generators ────────────────────────────────────────────────────────

async def stream_website_claude(prompt: str) -> AsyncGenerator[str, None]:
    user_msg = (
        f"Build a premium, high-converting website for: {prompt}. "
        "Make it feel like a $50k/year SaaS product. Output ONLY raw HTML."
    )
    async for chunk in _claude_stream(WEBSITE_SYSTEM, user_msg):
        yield chunk


async def stream_refine_claude(current_code: str, prompt: str) -> AsyncGenerator[str, None]:
    user_msg = f"EXISTING HTML:\n{current_code}\n\nUSER REQUEST:\n{prompt}"
    async for chunk in _claude_stream(REFINE_SYSTEM, user_msg):
        yield chunk


# ─── Fullstack frontend system prompt ────────────────────────────────────────

FULLSTACK_FRONTEND_SYSTEM = """You are a World-Class Senior Full-Stack UI Engineer.
Generate a COMPLETE, PRODUCTION-GRADE frontend application as a single self-contained HTML file.

TECH STACK (all via CDN — NO build step, runs in browser):
- React 18 + ReactDOM via: https://unpkg.com/react@18/umd/react.development.js
- React Router DOM 6 shim using state-based routing (NO BrowserRouter — use hash-based or state)
- Tailwind CSS: https://cdn.tailwindcss.com
- Lucide icons: https://unpkg.com/lucide@latest/dist/umd/lucide.js
- Font Awesome 6: https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css
- Google Fonts: Inter, Plus Jakarta Sans

APP ARCHITECTURE:
- Multi-page SPA using React state (currentPage / setCurrentPage) for routing — NO BrowserRouter
- Sidebar or top navbar with navigation links
- At minimum these pages/sections: Dashboard, main feature view, settings or profile, data list
- Use React.useState, React.useEffect, React.useCallback, React.useMemo as window.React.*
- Fetch data from http://localhost:8001/api/* with fallback to realistic hardcoded mock data if fetch fails
- Show loading spinners during fetch

DESIGN REQUIREMENTS (premium dark app):
- Background: #0a0c12 (near-black), card backgrounds: #0d1117 or #111827
- Accent: indigo-600 (#6366f1) with violet/purple gradients
- Glassmorphism cards: backdrop-filter blur, rgba borders
- Smooth hover effects on all interactive elements
- Sidebar with logo, nav items with icons, active state highlighting
- Top header bar with user avatar, breadcrumbs
- Rich data tables or card grids with badges, status pills, avatars
- Charts or stats panels using pure CSS/HTML (no chart library needed)

LAYOUT: Fixed sidebar (260px) + main content area with top header + scrollable content

CRITICAL OUTPUT RULES:
- Your response MUST begin with <!DOCTYPE html> as the VERY FIRST characters.
- Do NOT include ANY text before <!DOCTYPE html>. No planning. No scratchpad. No thinking. No explanations.
- Do NOT use markdown code fences (no ```html or ```).
- Do NOT write "Here is", "Let me", "I'll create", or ANY preamble text.
- Do NOT add comments explaining what you are doing.
- ONLY output the raw, valid HTML5 document from <!DOCTYPE html> to </html>.
- End with: const root = ReactDOM.createRoot(document.getElementById('root')); root.render(React.createElement(App));
- The entire app must work when pasted into a browser as an HTML file."""


def _strip_preamble(html: str) -> str:
    """Remove any non-HTML scratchpad/planning text before the actual HTML."""
    # Find the first HTML tag (<!DOCTYPE or <html or <head or <!)
    match = re.search(r'(?i)(<!doctype\s+html|<html|<!)', html)
    if match and match.start() > 0:
        return html[match.start():]
    return html


async def stream_fullstack_frontend_claude(prompt: str) -> AsyncGenerator[str, None]:
    """Stream a complete self-contained React app HTML file via Claude."""
    user_msg = (
        f"Build a complete, production-grade web application frontend for: {prompt}. "
        "Make it feel like a premium $200/month SaaS dashboard. "
        "Include realistic mock data. "
        "IMPORTANT: Start your response IMMEDIATELY with <!DOCTYPE html>. "
        "Do NOT include any text, planning, scratchpad, or explanation before the HTML. "
        "Output ONLY the raw HTML file."
    )
    # Track whether we've found the HTML start yet
    preamble_done = False
    buffer = ''

    async for chunk in _claude_stream(FULLSTACK_FRONTEND_SYSTEM, user_msg):
        if preamble_done:
            yield chunk
        else:
            buffer += chunk
            # Check if we've reached actual HTML content
            match = re.search(r'(?i)(<!doctype\s+html|<html|<!)', buffer)
            if match:
                preamble_done = True
                # Yield from the HTML start onward
                yield buffer[match.start():]
            # If buffer is getting large without finding HTML, flush it
            elif len(buffer) > 500:
                preamble_done = True
                yield buffer


def is_claude_configured() -> bool:
    return bool(
        settings.ANTHROPIC_API_KEY
        and not settings.ANTHROPIC_API_KEY.startswith("your-")
    )
