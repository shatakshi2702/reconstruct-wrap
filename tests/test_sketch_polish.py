"""Offline checks for the Sketch2UI design pass (no Groq call: ai_screens is stubbed).
Run: DATABASE_URL=sqlite+aiosqlite:///./t.db JWT_SECRET=t GROQ_API_KEY=x pytest tests
"""
import asyncio
import os

for key, value in {"DATABASE_URL": "sqlite+aiosqlite:///./t.db", "JWT_SECRET": "t", "GROQ_API_KEY": "x"}.items():
    os.environ.setdefault(key, value)

from app.services import sketch_polish as sp  # noqa: E402

RUNTIME = '<div id="s2u-toast"></div>\n<script>/* sketch2ui runtime */</script>'


def page(title, main):
    return (f"<!doctype html><html><head><title>{title}</title></head><body><main class=\"max-w-md\">\n"
            f"{main}\n</main>\n{RUNTIME}\n</body></html>")


INDEX = page("Login", """<nav><img src="logo.png" alt="Company logo" class="w-full"></nav>
<h1 class="font-semibold tracking-tight text-slate-900 text-3xl">Welcome back</h1>
<form aria-label="login"><input id="email" name="email" type="email" placeholder="Email">
<a href="dashboard.html" class="btn">Login</a></form>""")
DASH = page("Dashboard", '<h1>Dashboard</h1><button type="button" data-toast="Saved">Save</button>')


def run(coro):
    return asyncio.run(coro)


def test_theme_keeps_every_screen_and_the_runtime():
    html, used = run(sp.polish("Login Flow", INDEX, {"dashboard.html": DASH}, "theme"))
    assert used == "theme"
    assert 'data-screen="index.html"' in html and 'data-screen="dashboard.html"' in html
    assert "sketch2ui runtime" in html and "__sketch2uiGo" in html
    assert 'href="dashboard.html"' in html and 'data-toast="Saved"' in html
    assert "logo.png" not in html  # broken relative logo became a brand mark
    pages = sp.ordered_pages(INDEX, {"dashboard.html": DASH})
    assert not sp.missing(sp.screens_markup(pages, "Login Flow"), sp.theme_site("Login Flow", pages))


def test_none_returns_the_page_untouched():
    assert run(sp.polish("x", INDEX, None, "none")) == (INDEX, "none")


def test_good_ai_redesign_is_used(monkeypatch):
    async def fake(markup, name):
        return markup.replace("<h1", '<h1 data-x="1"').replace("<section", '<section class="bg-indigo-50"')
    monkeypatch.setattr(sp, "ai_screens", fake)
    html, used = run(sp.polish("Login Flow", INDEX, {"dashboard.html": DASH}, "ai"))
    assert used == "ai" and 'class="bg-indigo-50"' in html


def test_ai_redesign_that_drops_content_falls_back(monkeypatch):
    async def lossy(markup, name):
        return markup.replace('href="dashboard.html"', 'href="#"').replace("Welcome back", "Hello")
    monkeypatch.setattr(sp, "ai_screens", lossy)
    assert run(sp.polish("Login Flow", INDEX, {"dashboard.html": DASH}, "ai"))[1] == "theme"


def test_ai_error_falls_back(monkeypatch):
    async def boom(markup, name):
        raise ConnectionError("offline")
    monkeypatch.setattr(sp, "ai_screens", boom)
    assert run(sp.polish("Login Flow", INDEX, None, "ai"))[1] == "theme"


def test_missing_spots_lost_parts_and_added_scripts():
    original = sp.screens_markup({"index.html": INDEX}, "App")
    assert sp.missing(original, original) == []
    lost = sp.missing(original, original.replace('name="email"', "") + "<script>x</script>")
    assert "name=email" in lost and "added a <script>" in lost


def test_odd_page_names_are_ignored():
    assert list(sp.ordered_pages(INDEX, {"../evil.html": DASH, "about.html": DASH})) == ["index.html", "about.html"]
