"""separate host and event_creator schemas with least-privilege roles (Slice R1, #156)

Revision ID: d4e5f6a7b8c9
Revises: b8c9d0e1f2a3
Create Date: 2026-07-11 00:00:00.000000

Metadata-only prefactoring for the platform restructure: introduces the `host` and
`event_creator` Postgres schemas, moves the existing tables/enum types into them via
`ALTER ... SET SCHEMA` (no row rewrite), and creates two least-privilege, NOLOGIN roles that
document/enforce the intended per-schema ownership at the DB layer ahead of the later service
split. The running app keeps using its existing (admin) DATABASE_URL connection unchanged -
these roles aren't wired into the app in this slice.

Table -> schema mapping:
  host          : users, oauth_accounts
  event_creator : storage_configs, llm_prompts, processing_runs, processing_steps, events
                  (+ their enum types: storage_provider, processing_run_status,
                  processing_step_status)

`event_creator_app` gets REFERENCES-only on `host.users` (not SELECT) - the cross-schema FK
`event_creator.*.user_id -> host.users.id` keeps enforcing ON DELETE CASCADE regardless of that
role's own privileges (FK enforcement is independent of the querying role), so this grant is
purely the least-privilege documentation the design calls for.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HOST_TABLES = ["users", "oauth_accounts"]
_EVENT_CREATOR_TABLES = [
    "storage_configs",
    "llm_prompts",
    "processing_runs",
    "processing_steps",
    "events",
]
_EVENT_CREATOR_ENUMS = [
    "storage_provider",
    "processing_run_status",
    "processing_step_status",
]


def _grant_full_schema_access(schema: str, role: str, enums: list[str] | None = None) -> None:
    """Grant a role full R/W on a schema's current + future tables/sequences (and enum types,
    if any) - the "owning app" side of the least-privilege split."""
    op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
    op.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {role}")
    op.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema} TO {role}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {role}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {role}")
    # Postgres has no "GRANT ... ON ALL TYPES IN SCHEMA" shorthand (unlike TABLES/SEQUENCES), so
    # enum types are granted individually.
    for enum_name in enums or []:
        op.execute(f"GRANT USAGE ON TYPE {schema}.{enum_name} TO {role}")
    if enums:
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT USAGE ON TYPES TO {role}")


def _revoke_full_schema_access(schema: str, role: str, enums: list[str] | None = None) -> None:
    """Reverse of _grant_full_schema_access, in dependency-safe order (default privileges before
    the grants they modify, schema/table grants last) so the role can then be dropped cleanly."""
    if enums:
        op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE USAGE ON TYPES FROM {role}")
    for enum_name in enums or []:
        op.execute(f"REVOKE USAGE ON TYPE {schema}.{enum_name} FROM {role}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM {role}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {role}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {role}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {role}")
    op.execute(f"REVOKE USAGE ON SCHEMA {schema} FROM {role}")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS host")
    op.execute("CREATE SCHEMA IF NOT EXISTS event_creator")

    for table in _HOST_TABLES:
        op.execute(f"ALTER TABLE public.{table} SET SCHEMA host")

    for table in _EVENT_CREATOR_TABLES:
        op.execute(f"ALTER TABLE public.{table} SET SCHEMA event_creator")

    for enum_name in _EVENT_CREATOR_ENUMS:
        op.execute(f"ALTER TYPE public.{enum_name} SET SCHEMA event_creator")

    # DO blocks (not CREATE ROLE IF NOT EXISTS - Postgres has no such syntax) so re-running this
    # migration against a DB that already has the roles is a no-op rather than an error.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'host_app') THEN
                CREATE ROLE host_app NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'event_creator_app') THEN
                CREATE ROLE event_creator_app NOLOGIN;
            END IF;
        END
        $$;
        """
    )

    _grant_full_schema_access("host", "host_app")
    _grant_full_schema_access("event_creator", "event_creator_app", enums=_EVENT_CREATOR_ENUMS)

    # Narrow cross-schema grant: event_creator_app can be referenced by / reference host.users
    # for the FK, but cannot SELECT it. USAGE on the host schema is just name resolution, not
    # table access.
    op.execute("GRANT USAGE ON SCHEMA host TO event_creator_app")
    op.execute("GRANT REFERENCES ON host.users TO event_creator_app")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("REVOKE REFERENCES ON host.users FROM event_creator_app")
    op.execute("REVOKE USAGE ON SCHEMA host FROM event_creator_app")

    _revoke_full_schema_access("event_creator", "event_creator_app", enums=_EVENT_CREATOR_ENUMS)
    _revoke_full_schema_access("host", "host_app")

    op.execute("DROP ROLE IF EXISTS event_creator_app")
    op.execute("DROP ROLE IF EXISTS host_app")

    for enum_name in _EVENT_CREATOR_ENUMS:
        op.execute(f"ALTER TYPE event_creator.{enum_name} SET SCHEMA public")

    for table in _EVENT_CREATOR_TABLES:
        op.execute(f"ALTER TABLE event_creator.{table} SET SCHEMA public")

    for table in _HOST_TABLES:
        op.execute(f"ALTER TABLE host.{table} SET SCHEMA public")

    op.execute("DROP SCHEMA IF EXISTS event_creator")
    op.execute("DROP SCHEMA IF EXISTS host")
