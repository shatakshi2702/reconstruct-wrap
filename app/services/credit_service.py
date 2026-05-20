from fastapi import HTTPException
from app.models.credit_log import CreditLog

# Roles that never run out of credits
UNLIMITED_ROLES = {"developer", "admin"}

async def deduct_credit(db, user):
    # Developer / admin accounts have unlimited credits — skip deduction
    if user.role in UNLIMITED_ROLES:
        return

    if user.credits <= 0:
        raise HTTPException(status_code=403, detail="No credits left. Please upgrade your plan.")

    user.credits -= 1

    log = CreditLog(
        user_id=user.id,
        change_amount=-1,
        reason="Generation"
    )

    db.add(log)
