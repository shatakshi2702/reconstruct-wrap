import json
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.generation import Generation
from app.security.jwt_handler import verify_token
from app.schemas.generate_schema import GenerateSchema
from app.services.grok_service import (
    generate_text, generate_website, refine_website,
    generate_backend_code, generate_fullstack, extract_code_block
)
from app.services.claude_service import (
    stream_website_claude, stream_refine_claude,
    stream_fullstack_frontend_claude, is_claude_configured
)
from app.services.credit_service import deduct_credit

router = APIRouter(prefix="/generate")
security = HTTPBearer()


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _get_user(payload: dict) -> User | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == payload["user_id"]))
        return result.scalar_one_or_none()


def _require_payload(credentials: HTTPAuthorizationCredentials) -> dict:
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


# ─── POST /generate/stream  (Claude streaming – website) ─────────────────────

@router.post("/stream")
async def generate_stream(
    data: GenerateSchema,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Streams HTML generation token-by-token using Claude.
    SSE format: `data: {"chunk": "...token..."}\n\n`
    Ends with:  `data: [DONE]\n\n`
    On error:   `data: {"error": "..."}\n\n`
    """
    payload = _require_payload(credentials)

    # Collect chunks so we can persist after streaming completes
    chunks: list[str] = []
    start_time = time.time()

    async def event_stream():
        try:
            if data.type == "website":
                # True token-by-token streaming for websites
                async for token in stream_website_claude(data.prompt):
                    chunks.append(token)
                    yield f"data: {json.dumps({'chunk': token})}\n\n"

            elif data.type == "fullstack":
                # Claude streams the frontend live; Groq generates backend in parallel
                import asyncio

                # Start Groq backend generation as a background task
                backend_task = asyncio.create_task(generate_backend_code(data.prompt))

                # Stream Claude frontend tokens in real-time
                frontend_html = []
                async for token in stream_fullstack_frontend_claude(data.prompt):
                    frontend_html.append(token)
                    chunks.append(token)
                    yield f"data: {json.dumps({'chunk': token})}\n\n"

                # Claude done — send the preview HTML as a separate event
                preview_html = "".join(frontend_html)
                yield f"data: {json.dumps({'preview': preview_html})}\n\n"

                # Wait for Groq backend to finish
                try:
                    backend_output, _ = await backend_task
                    backend_serialized = (
                        backend_output if isinstance(backend_output, str)
                        else json.dumps(backend_output)
                    )
                    chunks.append(backend_serialized)
                    yield f"data: {json.dumps({'backend_payload': backend_serialized})}\n\n"
                except Exception as be:
                    yield f"data: {json.dumps({'backend_error': str(be)})}\n\n"

            elif data.type == "backend":
                # Groq generates backend; send heartbeat then full payload
                import asyncio
                working = True

                async def _hb():
                    while working:
                        await asyncio.sleep(1)

                hb = asyncio.create_task(_hb())
                try:
                    output, _ = await generate_backend_code(data.prompt)
                finally:
                    working = False
                    hb.cancel()

                serialized = output if isinstance(output, str) else json.dumps(output)
                chunks.append(serialized)
                yield f"data: {json.dumps({'payload': serialized, 'output_type': 'backend'})}\n\n"

            else:
                output, _ = await generate_text(data.prompt)
                serialized = output if isinstance(output, str) else json.dumps(output)
                chunks.append(serialized)
                yield f"data: {json.dumps({'payload': serialized, 'output_type': data.type})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    async def _save_to_db():
        """Runs after streaming completes (background task)."""
        full_output = "".join(chunks)
        response_ms = int((time.time() - start_time) * 1000)
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User).where(User.id == payload["user_id"])
                )
                user = result.scalar_one_or_none()
                if user:
                    await deduct_credit(db, user)
                    gen = Generation(
                        user_id=user.id,
                        prompt=data.prompt,
                        output=extract_code_block(full_output) if data.type == "website" else full_output,
                        type=data.type,
                        response_time=response_ms,
                    )
                    db.add(gen)
                    await db.commit()
        except Exception as e:
            print(f"[ERROR] Failed to save generation: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
        background=BackgroundTask(_save_to_db),
    )


# ─── POST /generate/refine-stream  (Claude streaming refine) ─────────────────

@router.post("/refine-stream")
async def refine_stream(
    data: GenerateSchema,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = _require_payload(credentials)

    if not data.current_code:
        raise HTTPException(status_code=400, detail="Missing current_code for refinement")

    chunks: list[str] = []
    start_time = time.time()

    async def event_stream():
        try:
            async for token in stream_refine_claude(data.current_code, data.prompt):
                chunks.append(token)
                yield f"data: {json.dumps({'chunk': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    async def _save_to_db():
        full_output = "".join(chunks)
        response_ms = int((time.time() - start_time) * 1000)
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User).where(User.id == payload["user_id"])
                )
                user = result.scalar_one_or_none()
                if user:
                    await deduct_credit(db, user)
                    gen = Generation(
                        user_id=user.id,
                        prompt=f"[Refine] {data.prompt}",
                        output=extract_code_block(full_output),
                        type="website",
                        response_time=response_ms,
                    )
                    db.add(gen)
                    await db.commit()
        except Exception as e:
            print(f"[ERROR] Failed to save refinement: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
        background=BackgroundTask(_save_to_db),
    )


# ─── GET /generate/status  (which AI engine is active) ───────────────────────

@router.get("/status")
async def generation_status():
    """
    Returns:
      engine: 'claude'         – Claude key valid + has credits
              'groq-fallback'  – Claude key set but no credits (Groq used)
              'groq'           – No Claude key configured at all
    """
    if not is_claude_configured():
        return {"engine": "groq", "claude_available": False, "streaming": True}

    # Quick probe – try streaming 1 token from Claude
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        async with client.messages.stream(
            model="claude-3-5-sonnet-20241022",
            max_tokens=5,
            messages=[{"role": "user", "content": "ping"}]
        ) as s:
            await s.get_final_text()
        return {"engine": "claude", "claude_available": True, "streaming": True}
    except Exception as e:
        err = str(e).lower()
        if "credit" in err or "billing" in err or "balance" in err:
            return {"engine": "groq-fallback", "claude_available": False, "streaming": True}
        return {"engine": "groq-fallback", "claude_available": False, "streaming": True}


# ─── POST /generate/refine  (legacy non-streaming refine) ────────────────────

@router.post("/refine")
async def refine(
    data: GenerateSchema,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    payload = _require_payload(credentials)

    if not data.current_code:
        raise HTTPException(status_code=400, detail="Missing current_code for refinement")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == payload["user_id"]))
        user = result.scalar_one()

        output, response_time = await refine_website(data.current_code, data.prompt)

        await deduct_credit(db, user)

        gen = Generation(
            user_id=user.id,
            prompt=f"Refine: {data.prompt}",
            output=output,
            type="website",
            response_time=response_time,
        )
        db.add(gen)
        await db.commit()

    return {"output": output, "response_time_ms": response_time}


# ─── POST /generate/  (legacy non-streaming generation) ──────────────────────

@router.post("/")
async def generate(
    data: GenerateSchema,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    print(f"DEBUG: generation request type='{data.type}' prompt='{data.prompt[:60]}'")

    payload = _require_payload(credentials)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == payload["user_id"]))
        user = result.scalar_one()

        if data.type == "website":
            output, response_time = await generate_website(data.prompt)
        elif data.type == "backend":
            output, response_time = await generate_backend_code(data.prompt)
        elif data.type == "fullstack":
            output, response_time = await generate_fullstack(data.prompt)
        else:
            output, response_time = await generate_text(data.prompt)

        await deduct_credit(db, user)

        db_output = output if isinstance(output, str) else json.dumps(output)

        gen = Generation(
            user_id=user.id,
            prompt=data.prompt,
            output=db_output,
            type=data.type,
            response_time=response_time,
        )
        db.add(gen)
        await db.commit()

    return {"output": output, "response_time_ms": response_time}
