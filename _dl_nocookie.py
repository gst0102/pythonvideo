"""无Cookie下载三平台视频"""
import logging, os, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("nocookie")

OUT = Path(__file__).resolve().parent / "down-video-no-cookie"
OUT.mkdir(exist_ok=True)

def safe(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()[:80] or "video"

def dl(platform, url):
    from core.video_service import VideoService
    logger.info("=" * 40)
    logger.info("下载 %s", platform)
    try:
        title, gen, hdrs = VideoService.create_stream_generator(url)
        fname = f"{platform}_{safe(title)}.mp4"
        fpath = OUT / fname
        total = 0
        with open(fpath, "wb") as f:
            for chunk in gen:
                f.write(chunk)
                total += len(chunk)
        logger.info("%s ✅ %.2f MB → %s", platform, total/1024/1024, fname)
    except Exception as e:
        logger.error("%s ❌ %s", platform, e)

if __name__ == "__main__":
    logger.info("输出目录: %s", OUT)
    dl("toutiao", "https://www.toutiao.com/video/7644411877657575955/")
    dl("douyin", "https://www.douyin.com/jingxuan?modal_id=7637891910186634559")
    dl("xhs", "http://xhslink.com/o/9MABJ0L7Yn8")
    logger.info("完成 → %s", OUT)