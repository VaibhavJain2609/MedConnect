from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# asyncpg connect args shared by both engines. Under PgBouncer
# pool_mode=transaction, server connections are recycled per transaction so
# asyncpg's client-side prepared-statement cache must be disabled
# (statement_cache_size=0), or queries fail with "prepared statement does not
# exist". Toggled by the DB_TRANSACTION_POOLING env var — see docs/pgbouncer.md.
_asyncpg_connect_args: dict = {"timeout": 10}
if settings.DB_TRANSACTION_POOLING:
    _asyncpg_connect_args["statement_cache_size"] = 0

# Main application database (users, doctors, prescriptions, medical records)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_asyncpg_connect_args,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Separate medicine database
medicine_engine = create_async_engine(
    settings.MEDICINE_DB_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_asyncpg_connect_args,
)
medicine_async_session = async_sessionmaker(medicine_engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for main application models."""
    pass


class MedicineBase(DeclarativeBase):
    """Base class for medicine database models."""
    pass


async def get_db():
    """Get main database session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_medicine_db():
    """Get medicine database session"""
    async with medicine_async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
