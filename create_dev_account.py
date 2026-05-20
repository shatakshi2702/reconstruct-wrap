import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy.future import select
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_dev_user():
    # Tables assumed to exist
    
    async with AsyncSessionLocal() as db:
        email = "dev@bobthebuilder.ai"
        
        # Check if exists
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"Updating existing user {email}...")
            user.credits = 999999999  # Effectively unlimited
            user.role = "developer"
        else:
            print(f"Creating new developer user {email}...")
            hashed_password = pwd_context.hash("dev123")
            user = User(
                email=email, 
                password=hashed_password, 
                role="developer", 
                credits=999999999
            )
            db.add(user)
            
        await db.commit()
        print("\n" + "="*40)
        print("✅ DEVELOPER ACCOUNT CREATED SUCCESSFULLY")
        print("="*40)
        print(f"📧 Email:    {email}")
        print(f"🔑 Password: dev123")
        print(f"💎 Credits:  Unlimited (999,999,999)")
        print("="*40)

if __name__ == "__main__":
    asyncio.run(create_dev_user())
