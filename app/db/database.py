"""
Database configuration and session management
Handles async SQLAlchemy engine and session creation
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import logging

from app.core.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

# Create async engine
# SQLite doesn't support connection pooling, so we use NullPool
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    poolclass=NullPool,  # Required for SQLite
    future=True
)

# Create async session factory
# This is similar to creating a SessionFactory in Hibernate
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db():
    """
    Initialize database - create all tables
    Called during application startup

    Similar to running Hibernate's hbm2ddl auto=create-drop
    or Spring Boot's spring.jpa.hibernate.ddl-auto=update
    """
    async with engine.begin() as conn:
        # Create all tables defined in models
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session

    Usage in FastAPI endpoints:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()

    This is similar to @Autowired EntityManager in Spring Boot
    The session is automatically closed after the request completes
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db():
    """
    Close database connections
    Called during application shutdown
    """
    await engine.dispose()
    logger.info("Database connections closed")
