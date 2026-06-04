# Phase 0 Baseline

## Purpose

This document freezes the Git and workspace boundary before starting the Yuexiang Stage 2 MVP changes.

It is a boundary record only:

- No business logic is changed here.
- No existing dirty changes are cleaned, stashed, or rewritten here.
- Existing dirty changes listed below must not be mixed into Stage 2 feature commits.

## Target Repository

- Repository path: `D:\Desktop\vedo-project\myproject`
- Remote: `git@github.com:gst0102/pythonvideo.git`
- Active branch after freeze: `feature/yuexiang-stage2-mvp`

## HEAD Baseline

- Branch before freeze: `master`
- Branch after freeze: `feature/yuexiang-stage2-mvp`
- HEAD before freeze: `41c35c6fedecfc9eef3b511510cb0b641463dc74`
- HEAD after freeze: `41c35c6fedecfc9eef3b511510cb0b641463dc74`

HEAD is intentionally unchanged during branch freeze. The branch was created from the current local `master` HEAD.

## Dirty Workspace Snapshot

The following changes already existed in the repository before Stage 2 implementation work began.

### Modified files

```text
DEPLOY.md
controllers/anime.py
controllers/user.py
core/douyin_service.py
core/kdocs_service.py
core/reverse_service.py
docker-compose.yml
main.py
models/__init__.py
schemas/user.py
services/config_service.py
services/payment_service.py
```

### Untracked files and directories

```text
controllers/ad.py
core/browser_guard.py
docs/
migrations/versions/006_ad_event_records.py
models/ad_event.py
services/ad_analytics_service.py
```

## Repo Policy For Stage 2

During Stage 2 MVP development:

1. Work must continue on `feature/yuexiang-stage2-mvp`.
2. Existing dirty changes above are treated as pre-existing history and must not be mixed into new Stage 2 commits.
3. New Stage 2 commits should stage only explicitly intended files.
4. No `stash`, `reset`, or cleanup action should be used to hide or discard the listed dirty state unless explicitly requested later.

## Scope Decision

This freeze applies only to:

- `D:\Desktop\vedo-project\myproject`

It does not yet apply to:

- `D:\Desktop\vedo-project\video-ts`

Reason:

- `video-ts` is a separate Git repository and does not point to `git@github.com:gst0102/pythonvideo.git`.
- If Stage 2 officially requires changes there, it should receive a separate Phase 0 branch freeze.
