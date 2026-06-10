"""Verify Stage 2 login and invite-binding flow.

Checks:
1. new user login auto-creates user and points account
2. first login with invite_code binds direct and indirect inviter
3. invite binding writes traceable invite_relations records
4. existing user re-login does not overwrite inviter binding
5. existing unbound user can bind once on later login
6. using own invite code on re-login does not self-bind
7. issued token is openid-based

By default it only prints the plan. Pass --execute to run against the current
database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jose import jwt  # noqa: E402

from jwt_create import ALGORITHM, SECRET_KEY, create_access_token  # noqa: E402
from models.base import async_session_factory  # noqa: E402
from models.invite_relation import InviteRelation  # noqa: E402
from models.user import User  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402
from services.user_service import UserService  # noqa: E402

REQUIRED_TABLES = {"users", "user_accounts", "invite_relations"}


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_true(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)


async def _invite_relations_for(session, invitee_id: uuid.UUID) -> list[InviteRelation]:
    result = await session.execute(select(InviteRelation).where(InviteRelation.invitee_id == invitee_id))
    return list(result.scalars().all())


async def verify() -> None:
    marker = f"stage2-login-{uuid.uuid4().hex[:10]}"

    async with async_session_factory() as session:
        try:
            await _assert_required_tables(session)

            root_user, root_is_new = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-root",
                nickname="Root Inviter",
                avatar="",
            )
            _assert_equal("root user is_new", root_is_new, True)
            root_account, _ = await PointsAccountService.ensure_user_account(session, root_user.id)
            _assert_equal("root account total_points", int(root_account.total_points), 0)

            direct_user, direct_is_new = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-direct",
                nickname="Direct Inviter",
                avatar="",
                invite_code=root_user.invite_code,
            )
            _assert_equal("direct inviter is_new", direct_is_new, True)
            _assert_equal("direct inviter parent_id", direct_user.parent_id, root_user.id)
            _assert_equal("direct inviter grand_parent_id", direct_user.grand_parent_id, None)
            direct_relations = await _invite_relations_for(session, direct_user.id)
            _assert_equal("direct relation count", len(direct_relations), 1)
            _assert_equal("direct relation inviter_id", direct_relations[0].inviter_id, root_user.id)
            _assert_equal("direct relation invite_code", direct_relations[0].invite_code, root_user.invite_code)
            _assert_equal("direct relation source", direct_relations[0].source, "login")

            invitee_user, invitee_is_new = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-invitee",
                nickname="Invitee",
                avatar="",
                invite_code=direct_user.invite_code,
            )
            _assert_equal("invitee is_new", invitee_is_new, True)
            _assert_equal("invitee parent_id", invitee_user.parent_id, direct_user.id)
            _assert_equal("invitee grand_parent_id", invitee_user.grand_parent_id, root_user.id)
            invitee_relations = await _invite_relations_for(session, invitee_user.id)
            _assert_equal("invitee relation count", len(invitee_relations), 1)
            _assert_equal("invitee relation inviter_id", invitee_relations[0].inviter_id, direct_user.id)
            _assert_equal("invitee relation invite_code", invitee_relations[0].invite_code, direct_user.invite_code)
            invitee_account, _ = await PointsAccountService.ensure_user_account(session, invitee_user.id)
            _assert_equal("invitee account total_points", int(invitee_account.total_points), 0)

            refreshed_root = await session.get(User, root_user.id)
            refreshed_direct = await session.get(User, direct_user.id)
            _assert_equal("root indirect_count", int(refreshed_root.indirect_count), 1)
            _assert_equal("root team_count", int(refreshed_root.team_count), 2)
            _assert_equal("direct invite_count", int(refreshed_direct.invite_count), 1)
            _assert_equal("direct team_count", int(refreshed_direct.team_count), 1)

            other_inviter, other_is_new = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-other",
                nickname="Other Inviter",
                avatar="",
            )
            _assert_equal("other inviter is_new", other_is_new, True)

            relogin_user, relogin_is_new = await UserService.get_or_create_user(
                session,
                openid=invitee_user.openid,
                nickname="Invitee Updated",
                avatar="avatar-updated",
                invite_code=other_inviter.invite_code,
            )
            _assert_equal("relogin is_new", relogin_is_new, False)
            _assert_equal("relogin parent_id unchanged", relogin_user.parent_id, direct_user.id)
            _assert_equal("relogin grand_parent_id unchanged", relogin_user.grand_parent_id, root_user.id)
            _assert_equal("relogin nickname updated", relogin_user.nickname, "Invitee Updated")
            _assert_equal("relogin avatar updated", relogin_user.avatar, "avatar-updated")
            relogin_relations = await _invite_relations_for(session, invitee_user.id)
            _assert_equal("relogin relation count unchanged", len(relogin_relations), 1)
            _assert_equal("relogin relation inviter unchanged", relogin_relations[0].inviter_id, direct_user.id)

            late_user, late_is_new = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-late",
                nickname="Late Bind User",
                avatar="",
            )
            _assert_equal("late user is_new", late_is_new, True)
            _assert_equal("late user initially unbound", late_user.parent_id, None)
            late_bound_user, late_bound_is_new = await UserService.get_or_create_user(
                session,
                openid=late_user.openid,
                nickname="Late Bind User",
                avatar="",
                invite_code=other_inviter.invite_code,
            )
            _assert_equal("late bind relogin is_new", late_bound_is_new, False)
            _assert_equal("late bind parent_id", late_bound_user.parent_id, other_inviter.id)
            late_relations = await _invite_relations_for(session, late_user.id)
            _assert_equal("late bind relation count", len(late_relations), 1)
            _assert_equal("late bind relation inviter_id", late_relations[0].inviter_id, other_inviter.id)

            late_rebind_user, late_rebind_is_new = await UserService.get_or_create_user(
                session,
                openid=late_user.openid,
                nickname="Late Bind User",
                avatar="",
                invite_code=root_user.invite_code,
            )
            _assert_equal("late rebind is_new", late_rebind_is_new, False)
            _assert_equal("late rebind parent_id unchanged", late_rebind_user.parent_id, other_inviter.id)
            late_rebind_relations = await _invite_relations_for(session, late_user.id)
            _assert_equal("late rebind relation count unchanged", len(late_rebind_relations), 1)

            solo_user, solo_is_new = await UserService.get_or_create_user(
                session,
                openid=f"{marker}-solo",
                nickname="Solo User",
                avatar="",
            )
            _assert_equal("solo user is_new", solo_is_new, True)
            solo_relogin, solo_relogin_is_new = await UserService.get_or_create_user(
                session,
                openid=solo_user.openid,
                nickname="Solo User Again",
                avatar="",
                invite_code=solo_user.invite_code,
            )
            _assert_equal("solo relogin is_new", solo_relogin_is_new, False)
            _assert_equal("self invite parent_id remains none", solo_relogin.parent_id, None)
            solo_relations = await _invite_relations_for(session, solo_user.id)
            _assert_equal("self invite relation not created", len(solo_relations), 0)

            token = create_access_token({"openid": invitee_user.openid})
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            _assert_equal("token payload openid", payload.get("openid"), invitee_user.openid)
            _assert_true("token payload should not need user_id", "user_id" not in payload)

            all_users_result = await session.execute(select(User).where(User.openid.like(f"{marker}%")))
            created_users = list(all_users_result.scalars().all())
            _assert_equal("created user count", len(created_users), 6)

            print("Login and invite verification passed")
            print("checks=new user, invite trace, no rebind, late bind, no self-bind, token openid")
        finally:
            await session.rollback()


async def _assert_required_tables(session) -> None:
    connection = await session.connection()
    table_names = await connection.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    missing = sorted(REQUIRED_TABLES - table_names)
    if missing:
        raise RuntimeError(
            "Missing required tables for login/invite verification: "
            + ", ".join(missing)
            + ". Run the Stage 2 Alembic migrations against the intended database first."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Stage 2 login and invite-binding flow.")
    parser.add_argument("--execute", action="store_true", help="run verification against the configured database")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute:
        print("Dry run only. Re-run with --execute to verify against the configured database.")
        print("Checks: new user init, invite trace, no rebind, late bind, no self-bind, token openid.")
        return

    try:
        asyncio.run(verify())
    except RuntimeError as exc:
        print(f"Verification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
