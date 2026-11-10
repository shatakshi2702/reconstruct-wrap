"""Drop-in router for Restruct Warp (Step 46): Sketch2UI's "Open in Restruct Warp" button posts here.

Copy to reconstruct-wrap/app/routers/sketch_import.py and add to its main.py:
    from app.routers import sketch_import
    app.include_router(sketch_import.router)

The page is saved as an ordinary "website" generation, so it shows up in /dashboard/history and
opens in the editor like any other. Importing costs no credit: no LLM call is made.
The UIDocument rides along inside the HTML (a JSON <script> tag), so no new column is needed and
the editor can read it back later.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.models.generation import Generation
from app.models.user import User
from app.security.jwt_handler import verify_token

router = APIRouter(prefix="/generate")
security = HTTPBearer()

DOC_TAG = '<script type="application/json" id="sketch2ui-document">{}</script>'


class SketchImportSchema(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    html: str = Field(min_length=1, max_length=2_000_000)
    document: dict | None = None  # Sketch2UI's UIDocument (shared/component.schema.json)


def embed_document(html: str, document: dict | None) -> str:
    if not document:
        return html
    tag = DOC_TAG.format(json.dumps(document).replace("</", "<\/"))  # can't close the script early
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
        gen = Generation(user_id=user.id, prompt=f"Sketch2UI: {data.name}",
                         output=embed_document(data.html, data.document), type="website", response_time=0)
        db.add(gen)
        await db.commit()
        await db.refresh(gen)
    return {"generation_id": gen.id}
