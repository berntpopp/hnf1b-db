"""Create initial admin user for the application."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.password import get_password_hash
from app.core.config import settings
from app.models.user import User


async def create_admin_user() -> None:
    """Create or update admin user from environment settings."""
    admin_username = settings.ADMIN_USERNAME
    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_PASSWORD

    print(f"Creating/updating admin user: {admin_username}")

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as db:
        try:
            # Check if admin exists
            result = await db.execute(
                select(User).where(
                    (User.username == admin_username) | (User.email == admin_email)
                )
            )
            existing_admin = result.scalar_one_or_none()

            if existing_admin:
                print(f"Admin user exists (ID: {existing_admin.id}), updating...")
                existing_admin.hashed_password = get_password_hash(admin_password)
                existing_admin.role = "admin"
                existing_admin.is_active = True
                existing_admin.is_verified = True
                existing_admin.failed_login_attempts = 0
                existing_admin.locked_until = None
                await db.commit()
                print(f"✅ Admin user updated: {admin_username}")
            else:
                print("Creating new admin user...")
                admin_user = User(
                    email=admin_email,
                    username=admin_username,
                    hashed_password=get_password_hash(admin_password),
                    full_name="Administrator",
                    role="admin",
                    is_active=True,
                    is_verified=True,
                )
                db.add(admin_user)
                await db.commit()
                await db.refresh(admin_user)
                print(f"✅ Admin user created: {admin_username} (ID: {admin_user.id})")

            print("\n🔐 Login credentials:")
            print(f"   Username: {admin_username}")
            print(f"   Password: {admin_password}")
            print(
                "\n⚠️  SECURITY: Change the admin password immediately "
                "after first login!\n"
            )

        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
            await db.rollback()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin_user())
