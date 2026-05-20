from sqlalchemy.future import select
from app.models.generation import Generation

async def get_user_generations(db, user_id):
    result = await db.execute(
        select(Generation).where(Generation.user_id == user_id)
    )
    return result.scalars().all()
