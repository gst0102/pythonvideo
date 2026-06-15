"""Resource classification helpers for collected netdisk assets."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


PRIMARY_CATEGORIES = [
    "影视剧",
    "自媒体素材",
    "编程课程",
    "AI工具",
    "电商运营",
    "学习办公",
    "养生健康",
    "软件工具",
    "本地生活",
    "其他资源",
]

MEDIA_COMPLETE_RE = re.compile(r"(完结|全集|全季|合集|珍藏版|收藏版|完整版|全\s*\d+\s*(?:集|话|期|季))", re.I)
MEDIA_UPDATING_RE = re.compile(r"(更\s*\d+|更新至\s*\d+|连载|未完结|持续更新)", re.I)

TITLE_NOISE_PATTERNS = [
    r"[\[\]【】()（）《》<>「」『』]",
    r"\b(?:4k|8k|1080p|2160p|720p|hdr|hevc|h\.?265|h\.?264|高码|中字|国语|粤语|双语|蓝光|web-?dl|remux)\b",
    r"(?:更新至|更)\s*\d+\s*(?:集|话|期)?",
    r"(?:完结|全集|全季|合集|珍藏版|收藏版|完整版)",
    r"第\s*\d+\s*(?:季|部)",
]

RULES: list[tuple[str, list[str], list[str]]] = [
    ("影视剧", ["电影", "电视剧", "番剧", "动漫", "纪录片", "1080p", "4k", "全集", "完结", "更新至", "中字", "蓝光"], ["影视", "视频"]),
    ("自媒体素材", ["自媒体", "短视频", "剪辑", "脚本", "选题", "爆款", "小红书", "抖音", "快手", "视频号", "封面"], ["短视频", "运营"]),
    ("编程课程", ["python", "java", "前端", "后端", "编程", "代码", "算法", "开发", "docker", "linux", "数据库", "react", "vue", "go语言"], ["编程", "课程"]),
    ("AI工具", ["ai", "chatgpt", "deepseek", "提示词", "大模型", "绘图", "stable diffusion", "comfyui", "midjourney"], ["AI", "工具"]),
    ("电商运营", ["电商", "淘宝", "拼多多", "闲鱼", "小店", "直播带货", "商品卡", "店铺", "运营课"], ["电商", "运营"]),
    ("学习办公", ["excel", "ppt", "word", "简历", "模板", "考研", "教资", "公考", "资料", "课件", "办公"], ["学习", "办公"]),
    ("养生健康", ["养生", "中医", "经络", "瑜伽", "健身", "减脂", "食疗", "健康", "睡眠", "康复"], ["养生", "健康"]),
    ("软件工具", ["软件", "插件", "工具", "激活", "安装包", "mac", "windows", "安卓", "脚本工具"], ["软件", "工具"]),
    ("本地生活", ["本地", "探店", "餐饮", "旅游", "民宿", "门店", "社区", "团购"], ["本地生活"]),
]


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    tags: list[str]
    confidence: int
    used_deepseek: bool = False


def normalize_resource_title(title: str) -> str:
    value = (title or "").lower()
    for pattern in TITLE_NOISE_PATTERNS:
        value = re.sub(pattern, "", value, flags=re.I)
    value = re.sub(r"[\s\-_.,，。:：;；/\\|]+", "", value)
    return value[:180]


def media_level_and_cost(title: str, text: str = "") -> tuple[str, int, list[str]]:
    content = f"{title}\n{text}"
    tags: list[str] = ["影视"]
    if MEDIA_UPDATING_RE.search(content):
        tags.append("未更新完结")
        return "normal", 5, tags
    if MEDIA_COMPLETE_RE.search(content):
        tags.append("完结")
        return "official", 20, tags
    return "normal", 5, tags


def classify_by_rules(title: str, text: str = "", netdisk: str = "") -> ClassificationResult:
    content = f"{title}\n{text}\n{netdisk}".lower()
    best_category = "其他资源"
    best_tags: list[str] = []
    best_score = 0
    for category, keywords, tags in RULES:
        score = sum(1 for keyword in keywords if keyword.lower() in content)
        if score > best_score:
            best_category = category
            best_tags = list(tags)
            best_score = score
    confidence = min(95, 45 + best_score * 18) if best_score else 35
    if best_category == "影视剧":
        _, _, media_tags = media_level_and_cost(title, text)
        best_tags = sorted(set([*best_tags, *media_tags]))
        if MEDIA_COMPLETE_RE.search(content) or MEDIA_UPDATING_RE.search(content):
            confidence = max(confidence, 82)
    return ClassificationResult(best_category, best_tags, confidence)


async def classify_resource(title: str, text: str = "", netdisk: str = "") -> ClassificationResult:
    rule_result = classify_by_rules(title, text, netdisk)
    threshold = int(os.getenv("RESOURCE_RULE_CONFIDENCE_THRESHOLD", "75"))
    if rule_result.confidence >= threshold:
        return rule_result
    deepseek_result = await _classify_with_deepseek(title, text, netdisk)
    return deepseek_result or rule_result


async def _classify_with_deepseek(title: str, text: str, netdisk: str) -> ClassificationResult | None:
    if os.getenv("DEEPSEEK_CLASSIFIER_ENABLED", "true").lower() != "true":
        return None
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    prompt = _build_deepseek_prompt(title, text, netdisk)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是资源库分类助手，只输出 JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
    return _parse_deepseek_classification(content)


def _build_deepseek_prompt(title: str, text: str, netdisk: str) -> str:
    return (
        "请给网盘资源分类。只允许输出 JSON，不要解释。\n"
        f"可选一级分类：{','.join(PRIMARY_CATEGORIES)}。\n"
        "输出格式：{\"category\":\"影视剧\",\"tags\":[\"标签1\"],\"confidence\":80}\n"
        "要求：tags 用中文短词，最多 5 个；confidence 为 0-100。\n"
        f"标题：{title}\n"
        f"网盘：{netdisk}\n"
        f"正文摘要：{text[:800]}\n"
    )


def _parse_deepseek_classification(content: str) -> ClassificationResult | None:
    raw = (content or "").strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        raw = match.group(0)
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return None
    category = str(data.get("category") or "").strip()
    if category not in PRIMARY_CATEGORIES:
        category = "其他资源"
    raw_tags = data.get("tags") or []
    tags = [str(tag).strip()[:20] for tag in raw_tags if str(tag).strip()][:5] if isinstance(raw_tags, list) else []
    confidence = max(0, min(100, int(data.get("confidence") or 0)))
    return ClassificationResult(category=category, tags=tags, confidence=confidence, used_deepseek=True)
