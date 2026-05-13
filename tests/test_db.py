"""Tests for database models and reconciliation."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from project_health.config.loader import Config
from project_health.db.models import Base, Person, PersonIdentity
from project_health.db.reconcile import reconcile_persons_from_config


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_reconcile_persons(db_session: AsyncSession):
    config = Config.model_validate({
        "team": [
            {"name": "Alice", "github": "alice-gh"},
            {"name": "Bob", "github": "bob-gh", "jira": "123"},
        ],
        "credentials": {"github_token": "token"},
    })

    await reconcile_persons_from_config(db_session, config)

    # Check persons created
    from sqlalchemy import select
    result = await db_session.execute(select(Person))
    persons = result.scalars().all()
    assert len(persons) == 2
    names = {p.display_name for p in persons}
    assert names == {"Alice", "Bob"}

    # Check identities created
    result = await db_session.execute(select(PersonIdentity))
    identities = result.scalars().all()
    assert len(identities) == 3  # Alice(gh) + Bob(gh) + Bob(jira)

    # Check Alice has github identity
    alice = next(p for p in persons if p.display_name == "Alice")
    alice_identities = [i for i in identities if i.person_id == alice.id]
    assert len(alice_identities) == 1
    assert alice_identities[0].source == "github"
    assert alice_identities[0].external_id == "alice-gh"
