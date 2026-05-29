"""
番剧订阅接口 — /anime

使用自有 anime_resources + user_subscriptions 表，不依赖外部 API。
身份认证: 通过请求中的 openid 参数识别用户。

接口：
  POST   /anime/subscribe     — 订阅番剧
  POST   /anime/unsubscribe   — 取消订阅
  GET    /anime/subscriptions — 获取订阅 ID 列表（兼容旧接口）
  GET    /anime/subscribed    — 获取完整订阅列表（JOIN 番剧数据）
  GET    /anime/resources     — 获取自有数据库中的影视资源（type=movie|4k）
  GET    /anime/access        — 获取媒体解锁权限（基于用户邀请人数）
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, delete as sql_delete, func
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from datetime import datetime

from core.response import response
from models.user import User
from models.anime_resource import AnimeResource
from models.user_subscription import UserSubscription
from models.base import get_session

router = APIRouter(prefix="/anime", tags=["番剧订阅"])

# ── Schema ──

class SubscribeRequest(BaseModel):
    openid: str
    anime_id: str
    # 以下为番剧详情（订阅时传入，若 anime_resources 中尚不存在则自动写入）
    title: str | None = None
    quality: str | None = None
    episode: str | None = None
    status: str | None = None
    baidu_url: str | None = None
    baidu_password: str | None = None
    quark_url: str | None = None


class SubscriptionResponse(BaseModel):
    subscribed: bool
    count: int


class SubscribedItem(BaseModel):
    anime_id: str
    title: str
    quality: str | None = None
    episode: str | None = None
    status: str | None = None
    baidu_url: str | None = None
    baidu_password: str | None = None
    quark_url: str | None = None
    update_time: str | None = None
    is_subscribed: bool = True
    is_reminded: bool = False
    last_episode: str | None = None


# ── 工具 ──

async def _get_user(session: AsyncSession, openid: str) -> User | None:
    result = await session.execute(select(User).where(User.openid == openid))
    return result.scalar_one_or_none()


def _json_response(data=None, msg="SUCCESS"):
    """返回 HTTP 200 + code:0 的 JSON 响应"""
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"code": 0, "message": msg, "data": data or {}})


def _err_response(msg: str, code: int = 400):
    """返回业务错误（HTTP 200 + 非0 code，前端据此判断失败）"""
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"code": code, "message": msg, "data": {}})


async def _get_or_create_anime(
    session: AsyncSession, req: SubscribeRequest
) -> AnimeResource | None:
    """获取番剧资源，不存在则根据前端传入的数据自动创建"""
    result = await session.execute(
        select(AnimeResource).where(
            AnimeResource.anime_id == req.anime_id,
            AnimeResource.is_active == True,
        )
    )
    anime = result.scalar_one_or_none()
    if anime:
        return anime

    # 自动创建：前端浏览番剧库时已持有完整数据，订阅时一并传过来
    if not req.title:
        return None

    anime = AnimeResource(
        anime_id=req.anime_id,
        title=req.title,
        category="anime",
        quality=req.quality,
        episode=req.episode,
        status=req.status,
        baidu_url=req.baidu_url,
        baidu_password=req.baidu_password,
        quark_url=req.quark_url,
        is_active=True,
    )
    session.add(anime)
    await session.flush()
    return anime


def _format_time(dt) -> str | None:
    """将 datetime 转为 YYYY-MM-DD 字符串"""
    if not dt:
        return None
    if isinstance(dt, str):
        return dt[:10] if len(dt) >= 10 else dt
    return dt.strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════
#  订阅
# ══════════════════════════════════════════════════════════

@router.post("/subscribe", summary="订阅番剧")
async def subscribe(req: SubscribeRequest, session: AsyncSession = Depends(get_session)):
    user = await _get_user(session, req.openid)
    if not user:
        return _err_response("用户不存在", 400)

    # 获取或自动创建番剧资源
    anime = await _get_or_create_anime(session, req)
    if not anime:
        return _err_response("番剧不存在，订阅时请传入番剧标题", 400)

    # 写入订阅关系
    try:
        sub = UserSubscription(
            user_id=user.id,
            anime_id=req.anime_id,
            last_episode=anime.episode,
        )
        session.add(sub)
        await session.flush()

        # 同步更新旧 JSON 字段（向后兼容）
        subs: list = user.anime_subscriptions or []
        if req.anime_id not in subs:
            subs.append(req.anime_id)
            user.anime_subscriptions = subs
            session.add(user)

        await session.commit()

        # 统计总数
        count_result = await session.execute(
            select(UserSubscription).where(UserSubscription.user_id == user.id)
        )
        count = len(count_result.scalars().all())

    except IntegrityError:
        await session.rollback()
        # 已订阅，返回当前计数
        count_result = await session.execute(
            select(UserSubscription).where(UserSubscription.user_id == user.id)
        )
        count = len(count_result.scalars().all())
        return _json_response(
            data={"subscribed": True, "count": count},
            msg="已订阅该番剧",
        )

    return _json_response(
        data={"subscribed": True, "count": count},
        msg="订阅成功",
    )


# ══════════════════════════════════════════════════════════
#  取消订阅
# ══════════════════════════════════════════════════════════

@router.post("/unsubscribe", summary="取消订阅")
async def unsubscribe(req: SubscribeRequest, session: AsyncSession = Depends(get_session)):
    user = await _get_user(session, req.openid)
    if not user:
        return _err_response("用户不存在", 400)

    # 从 user_subscriptions 表中删除
    result = await session.execute(
        sql_delete(UserSubscription).where(
            UserSubscription.user_id == user.id,
            UserSubscription.anime_id == req.anime_id,
        )
    )

    # 同步更新旧 JSON 字段（向后兼容）
    subs: list = user.anime_subscriptions or []
    if req.anime_id in subs:
        subs.remove(req.anime_id)
        user.anime_subscriptions = subs
        session.add(user)

    await session.commit()

    # 统计总数
    count_result = await session.execute(
        select(UserSubscription).where(UserSubscription.user_id == user.id)
    )
    count = len(count_result.scalars().all())

    return _json_response(
        data={"subscribed": False, "count": count},
        msg="已取消订阅",
    )


# ══════════════════════════════════════════════════════════
#  获取订阅 ID 列表（兼容旧接口）
# ══════════════════════════════════════════════════════════

@router.get("/subscriptions", summary="获取订阅 ID 列表")
async def list_subscriptions(
    openid: str,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_user(session, openid)
    if not user:
        return _json_response(data={"subscriptions": []}, msg="用户不存在")

    result = await session.execute(
        select(UserSubscription.anime_id).where(
            UserSubscription.user_id == user.id,
        )
    )
    ids = [row[0] for row in result.all()]

    return _json_response(data={"subscriptions": ids})


# ══════════════════════════════════════════════════════════
#  获取完整订阅列表（新接口：JOIN 番剧数据）
# ══════════════════════════════════════════════════════════

@router.get("/subscribed", summary="获取完整订阅列表")
async def get_subscribed(
    openid: str,
    session: AsyncSession = Depends(get_session),
):
    """
    获取用户的完整订阅列表，包含番剧详细信息。

    与旧 /subscriptions 接口的区别：
      - 旧接口：只返回 anime_id 列表，前端需自行从外部 API 合并数据
      - 新接口：直接 JOIN anime_resources 表，一次返回完整数据
    """
    user = await _get_user(session, openid)
    if not user:
        return _json_response(data={"list": []}, msg="用户不存在")

    # LEFT JOIN user_subscriptions + anime_resources
    # 即使 anime_resources 暂缺数据，已订阅的也能展示
    result = await session.execute(
        select(UserSubscription, AnimeResource)
        .join(
            AnimeResource,
            UserSubscription.anime_id == AnimeResource.anime_id,
            isouter=True,
        )
        .where(UserSubscription.user_id == user.id)
        .order_by(UserSubscription.created_at.desc())
    )
    rows = result.all()

    items = []
    for sub, anime in rows:
        item = {
            "anime_id": sub.anime_id,
            "title": anime.title if anime else "",
            "quality": anime.quality if anime else None,
            "episode": anime.episode if anime else sub.last_episode,
            "status": anime.status if anime else None,
            "baidu_url": anime.baidu_url if anime else None,
            "baidu_password": anime.baidu_password if anime else None,
            "quark_url": anime.quark_url if anime else None,
            "update_time": _format_time(anime.source_update_time or anime.updated_at) if anime else None,
            "is_subscribed": True,
            "is_reminded": sub.is_reminded,
            "last_episode": sub.last_episode,
        }
        items.append(item)

    return _json_response(data={"list": items})


# ══════════════════════════════════════════════════════════
#  获取自有数据库影视资源（电影/4K）
# ══════════════════════════════════════════════════════════

@router.get("/resources", summary="获取影视资源")
async def get_resources(
    type: str = "movie",
    keyword: str = "",
    page: int = 1,
    page_size: int = 100,
    session: AsyncSession = Depends(get_session),
):
    """
    从自有 anime_resources 表中读取电影/4K 数据。

    参数:
      type: movie | 4k
      keyword: 模糊搜索标题
      page: 页码（默认 1）
      page_size: 每页数量（默认 100）
    """
    # 基础查询
    query = select(AnimeResource).where(
        AnimeResource.category == type,
        AnimeResource.is_active == True,
    )

    # 关键词搜索
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        query = query.where(AnimeResource.title.ilike(kw))

    # 总数
    count_query = select(AnimeResource).where(
        AnimeResource.category == type,
        AnimeResource.is_active == True,
    )
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        count_query = count_query.where(AnimeResource.title.ilike(kw))

    total_result = await session.execute(select(func.count()).select_from(count_query.subquery()))
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(AnimeResource.updated_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    rows = result.scalars().all()

    items = []
    for anime in rows:
        items.append({
            "anime_id": anime.anime_id,
            "title": anime.title,
            "quality": anime.quality,
            "episode": anime.episode,
            "status": anime.status,
            "baidu_url": anime.baidu_url,
            "baidu_password": anime.baidu_password,
            "quark_url": anime.quark_url,
            "update_time": _format_time(anime.source_update_time or anime.updated_at),
        })

    return _json_response(data={"total": total, "list": items})


# ══════════════════════════════════════════════════════════
#  获取媒体解锁权限
# ══════════════════════════════════════════════════════════

@router.get("/access", summary="获取媒体解锁权限")
async def get_media_access(
    openid: str,
    session: AsyncSession = Depends(get_session),
):
    """
    返回各媒体类型的解锁状态，基于用户的邀请人数。

    返回规则：
      - movie: invite_count_1 >= 3 解锁
      - anime_4k: invite_count_1 >= 5 解锁
    """
    user = await _get_user(session, openid)
    if not user:
        return _json_response(data={"rules": []}, msg="用户不存在")

    invite_count = user.invite_count or 0

    rules = [
        {
            "type": "movie",
            "name": "最新电影",
            "required_invites": 3,
            "description": "邀请3位好友后可查看最新电影",
            "invite_count": invite_count,
            "remaining_invites": max(0, 3 - invite_count),
            "unlocked": invite_count >= 3,
        },
        {
            "type": "anime_4k",
            "name": "4K影视",
            "required_invites": 5,
            "description": "邀请5位好友后可查看4K影视",
            "invite_count": invite_count,
            "remaining_invites": max(0, 5 - invite_count),
            "unlocked": invite_count >= 5,
        },
    ]

    return _json_response(data={"rules": rules})
