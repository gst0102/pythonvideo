"""
五平台逆向下载器 v5
输出4字段: { title, cover_url, hd_video_url, normal_video_url }

============================================================
原理说明:
============================================================

【小红书】Cookie链 & 签名绕过:
- Cookie链: xhslink.com(分享链接) 302跳转 → acw_tc cookie → 真实页面
- API签名: 完全绕过! 不走 /api/sns/web/v1/feed API (需要 X-S/X-T签名)
  而是直接用页面的 SSR __INITIAL_STATE__ JSON, 小程序后台渲染时
  已经注入了完整笔记数据(标题/封面/视频流)
- 封面: xhscdn.com CDN需要 session cookies + 保留 ! 后缀

【B站】公开API, 最简单:
- 纯Python, 无需cookie/签名/MCP浏览器
- API: /x/web-interface/view 获取标题+封面+CID
- API: /x/player/playurl?fnval=1 获取传统MP4(不分DASH, 音视频一体)
- 避免DASH: mcdn.bilivideo.cn CDN被拒, 传统MP4走bilivideo.com正常

【抖音】数据来源:
- 新版抖音完全JS客户端渲染, 纯Python拿不到任何数据
- 必须用 js-reverse-mcp 浏览器执行JS后从页面提取
- 视频流: 新版改用 DASH 分离音视频, H265编码
- 封面: douyinpic.com签名URL, 不能去掉~tplv-*后缀, 会破坏签名

【今日头条】数据来源:
- 和抖音一样纯客户端JS渲染, HTML是空壳(4883字节)
- 必须用 js-reverse-mcp 浏览器渲染后提取
- 封面: og:image meta标签, 视频: video标签src
- CDN为 toutiaovod.com, br参数被CDN忽略, 只有一种质量

【快手】数据来源:
- 纯客户端JS渲染, 必须用 js-reverse-mcp 浏览器渲染
- 短链302 → m.chenzhongtech.com → www.kuaishou.com
- 视频: video标签src (kwaicdn.com), 封面: video poster属性 (yximgs.com)
- 无需cookie, 只需Referer

============================================================
"""

import requests
import json
import re
import os
from urllib.parse import unquote

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/148.0.0.0 Safari/537.36'
)
SAVE_DIR = r'd:\Desktop\图片测试\js-nixiang'


# ============================================================
#  小红书
# ============================================================

def xiaohongshu(share_url):
    """纯Python, 通过SSR数据获取, 绕过API签名"""
    session = requests.Session()
    session.headers.update({'User-Agent': UA})

    # 获取 cookie 链
    r1 = session.get(share_url, allow_redirects=False, timeout=15)
    loc = r1.headers.get('Location', '')
    if not loc:
        return {'error': '无重定向'}
    if loc.startswith('/'):
        loc = 'https://www.xiaohongshu.com' + loc
    note_id = re.search(r'/item/([a-f0-9]+)', loc)
    note_id = note_id.group(1) if note_id else ''

    # 访问页面，提取 SSR 数据
    resp = session.get(loc, timeout=15)
    html = resp.text
    if '你访问的页面不见了' in html:
        return {'error': '被拦截'}

    pos = html.find('__INITIAL_STATE__=')
    if pos == -1:
        return {'error': '无数据'}
    pos = html.index('{', pos)
    depth = 0
    for i, ch in enumerate(html[pos:], pos):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: end = i + 1; break

    data = json.loads(html[pos:end].replace('undefined', 'null'))
    note_map = data.get('note', {}).get('noteDetailMap', {})
    keys = [k for k in note_map if k != 'null']
    if not keys:
        return {'error': '无笔记数据'}
    note = note_map[keys[0]].get('note', {})

    title = note.get('title') or note.get('displayTitle', '')
    cover_url = ''
    imgs = note.get('imageList') or note.get('image_list') or []
    if imgs:
        raw = imgs[0].get('urlDefault') or imgs[0].get('url_default') or ''
        cover_url = raw

    video_urls = []
    if note.get('type') == 'video':
        stream = note.get('video', {}).get('media', {}).get('stream', {})
        for codec in ['h264', 'h265', 'av1']:
            for item in stream.get(codec, []):
                url = item.get('masterUrl') or item.get('master_url') or ''
                br = item.get('bitrate') or item.get('bitRate') or 0
                size = item.get('size', 0)
                if url:
                    video_urls.append({
                        'url': url, 'codec': codec,
                        'bitrate': br, 'size_mb': round(size / 1024 / 1024, 2),
                    })

    video_urls.sort(key=lambda x: x['bitrate'] or 0, reverse=True)
    hd = video_urls[0] if video_urls else {}
    normal = video_urls[-1] if len(video_urls) > 1 else hd

    xhs_hdrs = {
        'User-Agent': UA,
        'Referer': loc,
        'Origin': 'https://www.xiaohongshu.com',
    }
    if cover_url:
        _dl(session, cover_url, f'xhs_cover_{note_id}.jpg', '小红书封面', xhs_hdrs)
    if hd:
        _dl(session, hd['url'], f'xhs_hd_{note_id}.mp4', '小红书高清', xhs_hdrs)
    if normal and normal != hd:
        _dl(session, normal['url'], f'xhs_normal_{note_id}.mp4', '小红书普清', xhs_hdrs)

    return {
        'platform': 'xiaohongshu', 'note_id': note_id,
        'title': title, 'cover_url': cover_url,
        'hd_video_url': hd.get('url', ''), 'hd_info': hd,
        'normal_video_url': normal.get('url', ''), 'normal_info': normal,
        'all_streams': video_urls,
    }


# ============================================================
#  B站 (纯API, 无需cookie/签名)
# ============================================================

def bilibili(bvid):
    """纯Python, 调用B站公开API"""
    hdrs = {
        'User-Agent': UA,
        'Referer': f'https://www.bilibili.com/video/{bvid}/',
        'Origin': 'https://www.bilibili.com',
    }

    r = requests.get(
        f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',
        headers=hdrs, timeout=10
    )
    if r.status_code != 200:
        return {'error': f'view API HTTP {r.status_code}'}
    data = r.json()
    if data.get('code') != 0:
        return {'error': f'view API code={data.get("code")}'}
    d = data['data']
    title = d['title']
    cover_url = 'https:' + d['pic'] if d['pic'].startswith('//') else d['pic'].replace('http://', 'https://', 1)
    cid = d['pages'][0]['cid']

    r2 = requests.get(
        f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=112&fnval=1&fourk=1',
        headers=hdrs, timeout=10
    )
    play = r2.json()
    if play.get('code') != 0:
        return {'error': f'playurl API code={play.get("code")}'}

    durl = play.get('data', {}).get('durl', [])
    video_urls = []
    for item in durl:
        url = item.get('url', '')
        if url:
            video_urls.append({
                'url': url,
                'codec': 'avc+h264',
                'bitrate': 0,
                'size_mb': round(item.get('size', 0) / 1024 / 1024, 2),
            })

    hd = video_urls[0] if video_urls else {}
    normal = video_urls[-1] if len(video_urls) > 1 else hd

    dl_hdrs = {
        'User-Agent': UA,
        'Referer': 'https://www.bilibili.com/',
    }
    if cover_url:
        _dl_raw(cover_url, f'bili_cover_{bvid}.jpg', 'B站封面', dl_hdrs)
    if hd:
        _dl_raw(hd['url'], f'bili_hd_{bvid}.mp4', 'B站高清', dl_hdrs)
    if normal and normal != hd:
        _dl_raw(normal['url'], f'bili_normal_{bvid}.mp4', 'B站普清', dl_hdrs)

    return {
        'platform': 'bilibili', 'video_id': bvid,
        'title': title, 'cover_url': cover_url,
        'hd_video_url': hd.get('url', ''), 'hd_info': hd,
        'normal_video_url': normal.get('url', ''), 'normal_info': normal,
        'all_streams': video_urls,
    }


# ============================================================
#  抖音 (来自MCP浏览器提取的数据)
# ============================================================

def douyin_from_mcp(title, cover_url, video_urls, video_id):
    """接收MCP浏览器提取的数据，输出4字段"""
    video_urls.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
    hd = video_urls[0] if video_urls else {}
    normal = video_urls[-1] if len(video_urls) > 1 else hd

    dy_hdrs = {
        'User-Agent': UA,
        'Referer': 'https://www.douyin.com/',
        'Origin': 'https://www.douyin.com',
        'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    if cover_url:
        _dl_raw(cover_url, f'dy_cover_{video_id}.jpg', '抖音封面', dy_hdrs)
    if hd:
        _dl_raw(hd['url'], f'dy_hd_{video_id}.mp4', '抖音高清', dy_hdrs)
    if normal and normal != hd:
        _dl_raw(normal['url'], f'dy_normal_{video_id}.mp4', '抖音普清', dy_hdrs)

    return {
        'platform': 'douyin', 'video_id': video_id,
        'title': title, 'cover_url': cover_url,
        'hd_video_url': hd.get('url', ''), 'hd_info': hd,
        'normal_video_url': normal.get('url', ''), 'normal_info': normal,
        'all_streams': video_urls,
    }


# ============================================================
#  今日头条 (来自MCP浏览器提取的数据)
# ============================================================

def toutiao_from_mcp(title, cover_url, video_url, video_id):
    """接收MCP浏览器提取的数据，输出4字段"""
    video_info = {'url': video_url, 'codec': '', 'bitrate': 0}
    hdrs = {
        'User-Agent': UA,
        'Referer': 'https://www.toutiao.com/',
        'Origin': 'https://www.toutiao.com',
        'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    if cover_url:
        _dl_raw(cover_url, f'tt_cover_{video_id}.jpg', '头条封面', hdrs)
    if video_url:
        _dl_raw(video_url, f'tt_hd_{video_id}.mp4', '头条高清', hdrs)

    return {
        'platform': 'toutiao', 'video_id': video_id,
        'title': title, 'cover_url': cover_url,
        'hd_video_url': video_url, 'hd_info': video_info,
        'normal_video_url': video_url, 'normal_info': video_info,
        'all_streams': [video_info],
    }


# ============================================================
#  快手 (来自MCP浏览器提取的数据)
# ============================================================

def kuaishou_from_mcp(title, cover_url, video_url, video_id):
    """接收MCP浏览器提取的数据，输出4字段"""
    video_info = {'url': video_url, 'codec': '', 'bitrate': 0}
    hdrs = {
        'User-Agent': UA,
        'Referer': 'https://www.kuaishou.com/',
        'Origin': 'https://www.kuaishou.com',
    }
    if cover_url:
        _dl_raw(cover_url, f'kwai_cover_{video_id}.jpg', '快手封面', hdrs)
    if video_url:
        _dl_raw(video_url, f'kwai_hd_{video_id}.mp4', '快手高清', hdrs)

    return {
        'platform': 'kuaishou', 'video_id': video_id,
        'title': title, 'cover_url': cover_url,
        'hd_video_url': video_url, 'hd_info': video_info,
        'normal_video_url': video_url, 'normal_info': video_info,
        'all_streams': [video_info],
    }


# ============================================================
#  下载
# ============================================================

def _dl(session, url, filename, label, headers):
    save_path = os.path.join(SAVE_DIR, filename)
    print(f'  [{label}] {filename}: {url[:100]}...', end='', flush=True)
    resp = session.get(url, headers=headers, stream=True, timeout=120)
    if resp.status_code != 200:
        print(f' 失败 (HTTP {resp.status_code})')
        return False
    total = int(resp.headers.get('content-length', 0))
    downloaded = 0
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
    size = os.path.getsize(save_path) / 1024 / 1024
    print(f' 完成 ({size:.2f}MB)')
    return True

def _dl_raw(url, filename, label, headers):
    save_path = os.path.join(SAVE_DIR, filename)
    print(f'  [{label}] {filename}: {url[:100]}...', end='', flush=True)
    resp = requests.get(url, headers=headers, stream=True, timeout=120)
    if resp.status_code != 200:
        print(f' 失败 (HTTP {resp.status_code})')
        return False
    total = int(resp.headers.get('content-length', 0))
    downloaded = 0
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
    size = os.path.getsize(save_path) / 1024 / 1024
    print(f' 完成 ({size:.2f}MB)')
    return True


# ============================================================
#  主入口
# ============================================================

if __name__ == '__main__':
    results = []

    # [1] 小红书
    print('─' * 50)
    print(' [1] 小红书')
    print('─' * 50)
    r = xiaohongshu('http://xhslink.com/o/3mPdxCGvrdY')
    results.append(('小红书', r))

    # [2] B站 — 纯API
    print('\n' + '─' * 50)
    print(' [2] B站')
    print('─' * 50)
    r = bilibili('BV1PGGU6kESv')
    results.append(('B站', r))

    # [3] 抖音 — 从MCP浏览器提取的数据
    print('\n' + '─' * 50)
    print(' [3] 抖音')
    print('─' * 50)
    dy_data = douyin_from_mcp(
        title='郭聪明实在太厉害了，把各大网红都请来了#内蒙古 #包头 #郭聪明',
        cover_url='https://p3-pc-sign.douyinpic.com/tos-cn-p-0015/oETIIazKnGAUsZt7kWLJB7UB8BTAeCgNIee9aI~tplv-dy-360p.jpeg?biz_tag=pcweb_cover&from=327834062&lk3s=138a59ce&s=PackSourceEnum_AWEME_DETAIL&sc=origin_cover&se=false&x-expires=1781388000&x-signature=ZT1O6jlZZ8dqhVL1GmeXWJlipVE%3D',
        video_urls=[
            {
                'url': 'https://v26-web.douyinvod.com/d58647d20b128a1d8408d42b672abedd/6a1ccc40/video/tos/cn/tos-cn-ve-15/o8FnIJAmRI9ePAABWOUB2GeCNAjZaTAeAAKLA7/media-video-hvc1/?a=6383&ch=0&cr=8&dr=0&er=1&lr=default&cd=0%7C0%7C0%7C3&cv=1&br=1307&bt=1307&cs=4&ds=4&mime_type=video_mp4&qs=0&rc=OTNmNGllaThpNTxoPDRpZEBpanh2PGw5cjdlOzMzNGkzM0AxMTY2MF8yXzAxYTA1YzIvYSNtZ2c2MmRzL2FhLS1kLWFzcw%3D%3D&btag=c0000e00028000&cquery=100w_100o&dy_q=1780185726&l=20260531080206E091F7997F96C7B21ED6',
                'codec': 'hvc1', 'bitrate': 1307, 'size_mb': 17.46,
            },
        ],
        video_id='7645618223697726756',
    )
    results.append(('抖音', dy_data))

    # [4] 今日头条 — 从MCP浏览器提取的数据
    print('\n' + '─' * 50)
    print(' [4] 今日头条')
    print('─' * 50)
    tt_data = toutiao_from_mcp(
        title='杨超越：我在厂里的时候，你这样的我一天能见七八个#杨超越#',
        cover_url='https://p3-sign.toutiaoimg.com/tos-cn-p-0015/oggADffEAEiDIAa9AAqgFBvCEj9mAPBd4AZwhw~tplv-pk90l89vgd-crop-center-v4:864:486.jpeg?_iz=31127&bid=674&from=ttvideo.&gid=7638782304382353946&lk3s=06827d14&x-expires=1780791804&x-signature=jgYIbLl58KJMVF7HeZl3mvqKjcA%3D',
        video_url='https://v9-web.toutiaovod.com/79a081c595a4a4378ac200424d2a6a5b/6a1b8d98/video/tos/cn/tos-cn-ve-15/owCBiBOrVA5WMYDaIQCdifuIDoDb1EATkAPegu/?a=24&ch=94349560412&cr=0&dr=0&er=0&lr=unwatermarked&net=5&cd=0%7C0%7C0%7C0&cv=1&br=1423&bt=1423&cs=0&ds=6&ft=1-MljQvnppftsvLdEsO.C_fauVq0Innxx0pc6B0-dVhNtQdHDDiM40LyxYhzqusZ.&mime_type=video_mp4&qs=0&rc=OGZnaTk6Nzg3NTg4Njc8Z0BpMzc2b3Y5cmxkOzMzNDlpM0AwNV5hYjQyX2ExYl41NmEwYSNiMWMyMmRzMGFhLS1kMGFzcw%3D%3D&btag=c0000e00008000&dy_q=1780187010&feature_id=f5241e7604dff1d9d6c943fd20bd51a2&l=20260531082329D349DB47E6E1793B4B6E',
        video_id='7638782304382353946',
    )
    results.append(('头条', tt_data))

    # [5] 快手 — 从MCP浏览器提取的数据
    print('\n' + '─' * 50)
    print(' [5] 快手')
    print('─' * 50)
    kw_data = kuaishou_from_mcp(
        title='老爸的区别对待有点大#潮流生活成长之星 #快成长计划 #快成长计划 #潮流生活成长之星',
        cover_url='https://p2.a.yximgs.com/upic/2026/04/05/12/BMjAyNjA0MDUxMjQ3MTJfMTczMDIyODYzXzE5MjI0Mjk2OTgxOV8xXzM=_B9d11fe0744dc07b6e3f4d8d7f8059fe4.jpg?tag=1-1780188740-xpcwebdetail-0-65ub7gal6l-fab8ddae35bdb1b4&clientCacheKey=3xya9m5tirn3jc9.jpg&di=JAmKEBQaRADwfG-Td8elYA==&bp=14944',
        video_url='https://v23-3.kwaicdn.com/upic/2026/04/05/12/BMjAyNjA0MDUxMjQ3MTJfMTczMDIyODYzXzE5MjI0Mjk2OTgxOV8xXzM=_b_B800c554b8b818f63bb72fd86cff267a1.mp4?pkey=AAVyNw4b8VRm9yfLWVq5M7C4P60G8zhYbnyU3Lec_EX8XKkEc-3aFLibTFnUOH3wZy42c3wdfdR3kFdOIxG1mLWswYbH9aN_8GdvBOgax55mjs4n864L8w44hE9RK2S0_gE&tag=1-1780188740-unk',
        video_id='3xuhytcjrj697ce',
    )
    results.append(('快手', kw_data))

    # 输出
    print('\n' + '=' * 60)
    print('  4字段汇总输出')
    print('=' * 60)
    for name, r in results:
        print(f'\n【{name}】')
        print(f'  title        : {r.get("title", "")}')
        print(f'  cover_url    : {r.get("cover_url", "")[:120]}')
        print(f'  hd_video_url : {r.get("hd_video_url", "")[:120]}')
        print(f'  normal_video : {r.get("normal_video_url", "")[:120]}')
        streams = r.get('all_streams', [])
        if streams:
            print(f'  streams ({len(streams)}个):')
            for s in streams:
                print(f'    [{s.get("codec", "?")}] br={s.get("bitrate","?")} size={s.get("size_mb","?")}MB')

    print(f'\n文件保存在: {SAVE_DIR}')