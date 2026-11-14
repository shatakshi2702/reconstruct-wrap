"""Drop-in router for Restruct Warp (Step 46): Sketch2UI's "Open in Restruct Warp" button posts here.

Copy to reconstruct-wrap/app/routers/sketch_import.py and add to its main.py:
    from app.routers import sketch_import
    app.include_router(sketch_import.router)

The page is saved as an ordinary "website" generation, so it shows up in /dashboard/history and
opens in the editor like any other. Importing costs no credit unless the AI design pass runs.
The UIDocument rides along inside the HTML (a JSON <script> tag), so no new column is needed and
the editor can read it back later.

Sketch2UI's pages are plain wireframes, so by default they get a design pass first
(app/services/sketch_polish.py): every screen goes into one page, an LLM redesigns it, and a
fixed theme is used when the LLM is unavailable or drops anything from the sketch.
"""
import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.models.credit_log import CreditLog
from app.models.generation import Generation
from app.models.user import User
from app.security.jwt_handler import verify_token
from app.services.credit_service import UNLIMITED_ROLES
from app.services.sketch_polish import polish

router = APIRouter(prefix="/generate")
security = HTTPBearer()

DOC_TAG = '<script type="application/json" id="sketch2ui-document">{}</script>'


class SketchImportSchema(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    html: str = Field(min_length=1, max_length=2_000_000)
    document: dict | None = None  # Sketch2UI's UIDocument (shared/component.schema.json)
    pages: dict[str, str] | None = None  # every screen, {"index.html": ..., "dashboard.html": ...}
    polish: Literal["ai", "theme", "none"] = "ai"  # ai falls back to theme


def embed_document(html: str, document: dict | None) -> str:
    if not document:
        return html
    tag = DOC_TAG.format(json.dumps(document).replace("</", "<\\/"))  # can't close the script early
    return html.replace("</body>", tag + "\n</body>", 1) if "</body>" in html else html + tag


@router.post("/import", status_code=201)
async def import_sketch(data: SketchImportSchema, credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == payload["user_id"]))).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="Log in to Restruct Warp with the same account first")
        # the AI pass is an LLM call, so it needs a credit like any generation; without one, the theme
        mode = data.polish
        if mode == "ai" and user.role not in UNLIMITED_ROLES and user.credits <= 0:
            mode = "theme"
        start = time.time()
        html, used = await polish(data.name, data.html, data.pages, mode)
        if used == "ai" and user.role not in UNLIMITED_ROLES:
            user.credits -= 1
            db.add(CreditLog(user_id=user.id, change_amount=-1, reason="Sketch2UI polish"))
        gen = Generation(user_id=user.id, prompt=f"Sketch2UI: {data.name}",
                         output=embed_document(html, data.document), type="website",
                         response_time=int((time.time() - start) * 1000))
        db.add(gen)
        await db.commit()
        await db.refresh(gen)
    return {"generation_id": gen.id, "polish": used}
