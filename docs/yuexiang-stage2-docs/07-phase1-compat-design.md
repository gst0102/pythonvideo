# Phase 1 Compatibility Design

## Goal

This phase prepares the Stage 2 MVP data foundation without breaking the current online logic.

The current production code still uses:

- `users.balance`
- `users.frozen_balance`
- `users.total_income`
- `users.total_withdrawn`
- `users.is_vip`
- `users.vip_expire_at`
- `orders`
- `commission_records`
- `withdraw_records`
- `ad_reward_records`
- `ad_event_records`

Stage 2 needs a points-first accounting model, but the current online project is still cash-first. The compatibility strategy in this phase is therefore:

1. Add new Stage 2 tables.
2. Keep all old online tables untouched.
3. Do not rename or delete old columns.
4. Do not backfill or switch runtime logic in this phase.
5. Reuse `system_configs` instead of introducing a second config table right now.

## Compatibility Decisions

### 1. Users table stays in place

`users` remains the single source of truth for:

- identity
- invite code
- current v1 VIP flags
- current v1 cash balance fields

No destructive change is allowed in this phase.

### 2. New Stage 2 account model is additive

Introduce a new points account layer:

- `user_accounts`
- `points_ledger`

These tables are additive and independent from the old cash fields in `users`.

Short-term rule:

- v1 cash logic keeps using `users.balance` and related fields
- Stage 2 points logic will later use `user_accounts` and `points_ledger`

This avoids breaking current withdrawal, commission, and VIP flows before Stage 2 services are fully migrated.

### 3. No `app_configs` table yet

The Stage 2 docs propose `app_configs`, but the live project already has `system_configs`.

To avoid parallel config tables in the same phase:

- keep `system_configs`
- add Stage 2 namespaced config records into `system_configs`

Planned config types for Stage 2 draft:

- `stage2_points_config`
- `stage2_task_config`
- `stage2_member_config`
- `stage2_invite_config`
- `stage2_withdraw_config`
- `stage2_media_rights_config`
- `stage2_video_config`

Current runtime code does not read these keys yet. They are seeded now so later phases can switch to them cleanly.

### 4. Ad analytics stays separate from Stage 2 business idempotency

Current ad tables:

- `ad_reward_records`
- `ad_event_records`

These are currently tied to analytics and reward-to-cash logic. Phase 1 does not replace them.

Decision:

- keep current ad tables unchanged
- defer a dedicated Stage 2 business ad table until the Stage 2 reward flow is implemented

### 5. Orders and VIP membership stay on current model

Current payment flow uses:

- `orders`
- `users.is_vip`
- `users.vip_expire_at`

Phase 1 does not introduce `member_orders` or `user_memberships` yet, because doing so now would require changing payment callback behavior.

Decision:

- keep current VIP runtime logic in place
- defer membership model split to the dedicated member phase

### 6. Withdrawal stays on current cash model for now

Current runtime withdrawal flow uses:

- `withdraw_records`
- `users.balance`
- `users.frozen_balance`

Phase 1 does not switch withdrawal to points.

Decision:

- keep the old cash withdrawal path running
- introduce only the points foundation now
- defer `withdraw_logs` and points-withdraw conversion to the withdrawal phase

## New Tables In This Phase

This phase adds only the minimum safe Stage 2 foundation tables:

- `user_accounts`
- `points_ledger`
- `checkin_records`
- `game_rounds`
- `daily_task_stats`

These are enough to support:

- points account initialization
- points detail records
- daily check-in
- game task reward idempotency
- daily task counters

## Deferred Tables

These are intentionally deferred to later phases:

- `member_plans`
- `user_memberships`
- `member_orders`
- `invite_relations`
- `invite_rebates`
- `withdraw_logs`
- `event_logs`
- Stage 2 business `ad_events`

Reason:

- they either overlap heavily with current live tables
- or they require runtime behavior changes beyond a safe foundation migration

## Migration Safety Rules

This phase follows the following safety rules:

1. No existing table is dropped.
2. No existing column is renamed.
3. No existing config type is rewritten.
4. New tables are isolated by foreign keys and unique indexes only.
5. New config records are namespaced under `stage2_*`.

## Runtime Follow-up

After this migration lands, the next implementation phase should:

1. Add model classes for the new tables.
2. Add a `PointsAccountService` abstraction.
3. Add user account lazy initialization on login.
4. Add check-in and game reward APIs using `points_ledger`.
5. Keep v1 cash APIs alive until the “我的”页 and withdrawal path are migrated.
