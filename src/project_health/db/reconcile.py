"""Boot-time identity reconciliation from YAML config into the database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.config.loader import Config, TeamMember
from project_health.db.models import Person, PersonIdentity


async def reconcile_persons_from_config(session: AsyncSession, config: Config) -> None:
    """Upsert persons and person_identities from YAML team list.

    Identities present in the database but no longer in YAML are left
    intact (person_id retained) for historical attribution.
    """
    # Fetch all existing identities
    existing_result = await session.execute(
        select(PersonIdentity.source, PersonIdentity.external_id, PersonIdentity.person_id)
    )
    existing_rows = {
        (row.source, row.external_id): row.person_id
        for row in existing_result.all()
    }

    # Build map of desired identities from YAML
    desired: dict[str, dict[str, str]] = {}  # display_name -> {source: external_id}
    for member in config.team:
        if member.name in desired:
            desired[member.name].update(_member_identities(member))
        else:
            desired[member.name] = _member_identities(member)

    # Upsert persons
    for name in desired:
        person_result = await session.execute(select(Person).where(Person.display_name == name))
        person = person_result.scalar_one_or_none()
        if person is None:
            person = Person(display_name=name, active=True)
            session.add(person)
            await session.flush()  # get person.id assigned
        else:
            person.active = True
            # ensure we have the ID loaded
            await session.refresh(person)

    await session.commit()

    # Re-fetch persons to get IDs
    person_map: dict[str, str] = {}
    for name in desired:
        person_result = await session.execute(select(Person).where(Person.display_name == name))
        person = person_result.scalar_one()
        person_map[name] = person.id

    # Upsert identities
    for name, identities in desired.items():
        person_id = person_map[name]
        for source, external_id in identities.items():
            key = (source, external_id)
            if key in existing_rows:
                # Update person_id if it changed (e.g. identity reassigned)
                identity_result = await session.execute(
                    select(PersonIdentity).where(
                        PersonIdentity.source == source,
                        PersonIdentity.external_id == external_id,
                    )
                )
                identity = identity_result.scalar_one()
                identity.person_id = person_id
                if source == "launchpad":
                    identity.display_name = identity.display_name or name
                    identity.profile_url = identity.profile_url or _launchpad_profile_url(external_id)
            else:
                new_identity = PersonIdentity(
                    person_id=person_id,
                    source=source,
                    external_id=external_id,
                    display_name=name if source == "launchpad" else None,
                    profile_url=_launchpad_profile_url(external_id) if source == "launchpad" else None,
                    data={},
                )
                session.add(new_identity)

    await session.commit()


def _member_identities(member: TeamMember) -> dict[str, str]:
    """Return mapping of source -> external_id for a team member."""
    result: dict[str, str] = {}
    if member.github:
        result["github"] = member.github
    if member.jira:
        result["jira"] = member.jira
    if member.launchpad:
        result["launchpad"] = member.launchpad
    return result


def _launchpad_profile_url(external_id: str) -> str:
    return f"https://launchpad.net/{external_id}"
