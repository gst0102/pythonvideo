"""Invite reward service with idempotent points ledger writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.invite_relation import InviteRelation
from models.points_ledger import PointsLedger
from models.user_account import UserAccount
from services.points_account_service import PointsAccountService

InviteRewardEvent = Literal["register", "first_resource", "first_recharge"]


@dataclass(frozen=True)
class InviteRewardRule:
    event: InviteRewardEvent
    points: int
    change_type: str
    remark: str


INVITE_REWARD_RULES: dict[InviteRewardEvent, InviteRewardRule] = {
    "register": InviteRewardRule(
        event="register",
        points=5,
        change_type="invite_register",
        remark="invite register reward",
    ),
    "first_resource": InviteRewardRule(
        event="first_resource",
        points=10,
        change_type="invite_first_resource",
        remark="invitee first resource reward",
    ),
    "first_recharge": InviteRewardRule(
        event="first_recharge",
        points=20,
        change_type="invite_first_recharge",
        remark="invitee first recharge reward",
    ),
}


class InviteRewardService:
    """Grant invite rewards once per relation and event.

    All rewards are written to points_ledger with a deterministic idempotency
    key. Replays return the original ledger and do not add points again.
    """

    @staticmethod
    async def grant_register_reward_for_relation(
        session: AsyncSession,
        relation: InviteRelation,
    ) -> tuple[PointsLedger, UserAccount, bool]:
        return await InviteRewardService._grant_reward(
            session=session,
            relation=relation,
            event="register",
            related_id=str(relation.invitee_id),
        )

    @staticmethod
    async def grant_first_resource_reward(
        session: AsyncSession,
        invitee_id: UUID,
        resource_id: str,
    ) -> tuple[PointsLedger | None, UserAccount | None, bool]:
        relation = await _get_relation_by_invitee(session, invitee_id)
        if not relation:
            return None, None, False
        return await InviteRewardService._grant_reward(
            session=session,
            relation=relation,
            event="first_resource",
            related_id=(resource_id or "").strip() or str(invitee_id),
        )

    @staticmethod
    async def grant_first_recharge_reward(
        session: AsyncSession,
        invitee_id: UUID,
        order_id: str,
    ) -> tuple[PointsLedger | None, UserAccount | None, bool]:
        relation = await _get_relation_by_invitee(session, invitee_id)
        if not relation:
            return None, None, False
        return await InviteRewardService._grant_reward(
            session=session,
            relation=relation,
            event="first_recharge",
            related_id=(order_id or "").strip() or str(invitee_id),
        )

    @staticmethod
    async def _grant_reward(
        session: AsyncSession,
        relation: InviteRelation,
        event: InviteRewardEvent,
        related_id: str,
    ) -> tuple[PointsLedger, UserAccount, bool]:
        rule = INVITE_REWARD_RULES[event]
        idempotency_key = f"invite:{event}:{relation.id}"
        return await PointsAccountService.add_points(
            session=session,
            user_id=relation.inviter_id,
            points=rule.points,
            source="invite",
            change_type=rule.change_type,
            availability="consumable",
            idempotency_key=idempotency_key,
            related_type="invite_relation",
            related_id=str(relation.id),
            remark=f"{rule.remark}; trigger={related_id}",
        )


async def _get_relation_by_invitee(session: AsyncSession, invitee_id: UUID) -> InviteRelation | None:
    result = await session.execute(select(InviteRelation).where(InviteRelation.invitee_id == invitee_id))
    return result.scalar_one_or_none()
