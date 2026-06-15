"""Verify paid-order invite equity and points rewards.

Default mode only prints the verification purpose. Pass --execute to run against
the configured database inside a rollback transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.base import async_session_factory  # noqa: E402
from models.commission import CommissionRecord  # noqa: E402
from models.invite_relation import InviteRelation  # noqa: E402
from models.netdisk_user_notification import NetdiskUserNotification  # noqa: E402
from models.order import Order  # noqa: E402
from models.points_ledger import PointsLedger  # noqa: E402
from models.user import User  # noqa: E402
from services.config_service import ConfigService  # noqa: E402
from services.payment_service import PaymentService  # noqa: E402
from services.points_account_service import PointsAccountService  # noqa: E402


def _assert_equal(label: str, actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _money(value) -> float:
    return round(float(value or 0), 2)


async def verify() -> None:
    marker = f"benefit-card-{uuid.uuid4().hex[:10]}"
    async with async_session_factory() as session:
        try:
            await ConfigService.set(session, "stage2_points_config", {"exchange_rate": 100})
            await ConfigService.set(session, "commission_settings", {"level1_rate": 50.0, "level2_rate": 5.0})

            inviter = User(openid=f"{marker}-inviter", nickname="Inviter", avatar="", invite_code=f"{marker}i"[-10:])
            buyer = User(
                openid=f"{marker}-buyer",
                nickname="Buyer",
                avatar="",
                invite_code=f"{marker}b"[-10:],
                parent_id=inviter.id,
            )
            session.add(inviter)
            session.add(buyer)
            await session.flush()
            session.add(
                InviteRelation(
                    inviter_id=inviter.id,
                    invitee_id=buyer.id,
                    invite_code=inviter.invite_code,
                    source="test",
                )
            )
            await session.flush()

            first_order = Order(
                user_id=buyer.id,
                amount=10.0,
                period="card_month_10",
                duration_days=30,
                description="10 yuan benefit card",
                out_trade_no=f"{marker}-card-1",
                status="pending",
            )
            session.add(first_order)
            await session.flush()

            ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=first_order.out_trade_no,
                transaction_id=f"{marker}-tx-1",
                total_fee_in_fen=1000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("first card payment", ok, True)

            buyer_after = await session.get(User, buyer.id)
            if not buyer_after or not buyer_after.is_vip or not buyer_after.vip_expire_at:
                raise AssertionError("benefit card should activate ad-free membership")

            buyer_account, _ = await PointsAccountService.ensure_user_account(session, buyer.id)
            _assert_equal("benefit card points", int(buyer_account.consumable_points), 300)

            duplicate_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=first_order.out_trade_no,
                transaction_id=f"{marker}-tx-1-duplicate",
                total_fee_in_fen=1000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("duplicate card callback", duplicate_ok, True)
            buyer_account_after_dup, _ = await PointsAccountService.ensure_user_account(session, buyer.id)
            _assert_equal("duplicate should not add card points", int(buyer_account_after_dup.consumable_points), 300)

            inviter_after = await session.get(User, inviter.id)
            if not inviter_after:
                raise AssertionError("inviter missing")
            _assert_equal("invite equity after first card order", _money(inviter_after.balance), 5.0)
            _assert_equal("invite total income after first card order", _money(inviter_after.total_income), 5.0)
            inviter_account_after_first, _ = await PointsAccountService.ensure_user_account(session, inviter.id)
            _assert_equal("invite points after first card order", int(inviter_account_after_first.frozen_points), 500)

            card_records_after_dup = (
                await session.execute(
                    select(CommissionRecord).where(
                        CommissionRecord.user_id == inviter.id,
                        CommissionRecord.from_user_id == buyer.id,
                    )
                )
            ).scalars().all()
            card_notifications_after_dup = (
                await session.execute(
                    select(NetdiskUserNotification).where(
                        NetdiskUserNotification.user_id == inviter.id,
                        NetdiskUserNotification.notice_type == "invite_equity_reward",
                    )
                )
            ).scalars().all()
            _assert_equal("duplicate card callback does not add commission", len(list(card_records_after_dup)), 1)
            _assert_equal("duplicate card callback does not add notification", len(list(card_notifications_after_dup)), 1)

            second_order = Order(
                user_id=buyer.id,
                amount=20.0,
                period="card_month_20",
                duration_days=30,
                description="20 yuan benefit card renewal",
                out_trade_no=f"{marker}-card-2",
                status="pending",
            )
            session.add(second_order)
            await session.flush()

            second_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=second_order.out_trade_no,
                transaction_id=f"{marker}-tx-2",
                total_fee_in_fen=2000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("second card payment", second_ok, True)

            inviter_after_second = await session.get(User, inviter.id)
            if not inviter_after_second:
                raise AssertionError("inviter missing after second payment")
            _assert_equal("same invitee new card order grants equity again", _money(inviter_after_second.balance), 15.0)
            _assert_equal("same invitee new card order increases total income", _money(inviter_after_second.total_income), 15.0)
            inviter_account_after_second, _ = await PointsAccountService.ensure_user_account(session, inviter.id)
            _assert_equal("same invitee new card order grants points again", int(inviter_account_after_second.frozen_points), 1500)

            second_duplicate_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=second_order.out_trade_no,
                transaction_id=f"{marker}-tx-2-duplicate",
                total_fee_in_fen=2000,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("duplicate second card callback", second_duplicate_ok, True)
            inviter_after_second_dup = await session.get(User, inviter.id)
            if not inviter_after_second_dup:
                raise AssertionError("inviter missing after second duplicate callback")
            _assert_equal("duplicate second card callback does not add equity", _money(inviter_after_second_dup.balance), 15.0)

            ledgers = (
                await session.execute(
                    select(PointsLedger).where(
                        PointsLedger.user_id == buyer.id,
                        PointsLedger.change_type == "benefit_card_points",
                    )
                )
            ).scalars().all()
            _assert_equal("benefit card ledger count", len(list(ledgers)), 2)

            records = (
                await session.execute(
                    select(CommissionRecord).where(
                        CommissionRecord.user_id == inviter.id,
                        CommissionRecord.from_user_id == buyer.id,
                    )
                )
            ).scalars().all()
            _assert_equal("commission records for two orders", len(list(records)), 2)

            notifications = (
                await session.execute(
                    select(NetdiskUserNotification).where(
                        NetdiskUserNotification.user_id == inviter.id,
                        NetdiskUserNotification.notice_type == "invite_equity_reward",
                    )
                )
            ).scalars().all()
            _assert_equal("equity notification count", len(list(notifications)), 2)

            points_order = Order(
                user_id=buyer.id,
                amount=1.0,
                period="points_10",
                duration_days=0,
                description="1 yuan points recharge",
                out_trade_no=f"{marker}-points-1",
                status="pending",
            )
            session.add(points_order)
            await session.flush()

            points_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=points_order.out_trade_no,
                transaction_id=f"{marker}-points-tx-1",
                total_fee_in_fen=100,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("points recharge payment", points_ok, True)
            points_duplicate_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=points_order.out_trade_no,
                transaction_id=f"{marker}-points-tx-1-duplicate",
                total_fee_in_fen=100,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("duplicate points recharge callback", points_duplicate_ok, True)

            inviter_after_points = await session.get(User, inviter.id)
            if not inviter_after_points:
                raise AssertionError("inviter missing after points recharge")
            _assert_equal("points recharge grants equity once", _money(inviter_after_points.balance), 15.5)
            points_inviter_account, _ = await PointsAccountService.ensure_user_account(session, inviter.id)
            _assert_equal("points recharge grants rebate points once", int(points_inviter_account.frozen_points), 1550)
            _assert_equal("first recharge fixed reward only once", int(points_inviter_account.consumable_points), 20)

            second_points_order = Order(
                user_id=buyer.id,
                amount=1.0,
                period="points_10",
                duration_days=0,
                description="1 yuan points recharge again",
                out_trade_no=f"{marker}-points-2",
                status="pending",
            )
            session.add(second_points_order)
            await session.flush()

            second_points_ok = await PaymentService.handle_payment_success(
                session,
                out_trade_no=second_points_order.out_trade_no,
                transaction_id=f"{marker}-points-tx-2",
                total_fee_in_fen=100,
                paid_at=datetime.now(timezone.utc).isoformat(),
            )
            _assert_equal("same invitee second points recharge payment", second_points_ok, True)

            inviter_after_second_points = await session.get(User, inviter.id)
            if not inviter_after_second_points:
                raise AssertionError("inviter missing after second points recharge")
            _assert_equal("same invitee second points recharge grants equity again", _money(inviter_after_second_points.balance), 16.0)
            second_points_inviter_account, _ = await PointsAccountService.ensure_user_account(session, inviter.id)
            _assert_equal("same invitee second points recharge grants rebate points again", int(second_points_inviter_account.frozen_points), 1600)
            _assert_equal("fixed first recharge reward still once", int(second_points_inviter_account.consumable_points), 20)

            final_records = (
                await session.execute(
                    select(CommissionRecord).where(
                        CommissionRecord.user_id == inviter.id,
                        CommissionRecord.from_user_id == buyer.id,
                    )
                )
            ).scalars().all()
            final_notifications = (
                await session.execute(
                    select(NetdiskUserNotification).where(
                        NetdiskUserNotification.user_id == inviter.id,
                        NetdiskUserNotification.notice_type == "invite_equity_reward",
                    )
                )
            ).scalars().all()
            _assert_equal("commission records for four paid orders", len(list(final_records)), 4)
            _assert_equal("equity notifications for four paid orders", len(list(final_notifications)), 4)

            await session.rollback()
            print("OK paid invite equity + points flow verified in rollback transaction")
            print(
                "checks=card points, card duplicate idempotency, same invitee card renewal rewards again, "
                "points recharge duplicate idempotency, same invitee second points recharge rewards again, "
                "fixed first recharge reward only once"
            )
        except Exception:
            await session.rollback()
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="run verification against configured database")
    args = parser.parse_args()
    if not args.execute:
        print("Dry run: pass --execute to verify paid invite equity + points flow.")
        return
    asyncio.run(verify())


if __name__ == "__main__":
    main()
