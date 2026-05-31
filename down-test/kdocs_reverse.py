"""
金山文档(kdocs) 爬虫 - 逆向 + 15分钟监控
========================================

核心接口: POST /api/v3/office/file/{fileId}/open/otl
参数来源: 页面 window.__WPSENV__ (conn_id, user_group, file_version, csrf_token)

update_time = 爬取时的当前时间 (如 "5月31日 14:30")
"""

import requests
import json
import re
import os
import time
import sys
from datetime import datetime

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/148.0.0.0 Safari/537.36'
)
SAVE_DIR = r'd:\Desktop\图片测试\js-nixiang'
SHARE_URL = 'https://www.kdocs.cn/l/co72a28MWkmI'
FILE_ID = '434428384518'
SHARE_CODE = 'co72a28MWkmI'


# ============================================================
#  工具函数
# ============================================================

def extract_text_nodes(block, texts=None):
    if texts is None:
        texts = []
    if isinstance(block, dict):
        if block.get('type') == 'text' and 'text' in block:
            texts.append(block['text'])
        if 'content' in block:
            for child in block['content']:
                extract_text_nodes(child, texts)
    elif isinstance(block, list):
        for child in block:
            extract_text_nodes(child, texts)
    return texts


# ============================================================
#  数据解析
# ============================================================

def parse_doc(doc_data, crawl_time):
    """解析文档 JSON，提取剧集条目"""
    content = doc_data.get('content', {}).get('content', [])
    if not content:
        return []

    entries = []
    all_texts = extract_text_nodes(content)

    SKIP_PREFIXES = [
        'http', '百度', '夸克', '提取码', '4K', '注意', '搜索', '解决',
        '①', '②', '③', '④', '⑤', '热门剧', '链接', '迅雷', '磁力',
    ]
    SKIP_KEYWORDS = ['登录', '查找和替换', '关键字', '搜不到']

    i = 0
    while i < len(all_texts):
        text = all_texts[i].strip()

        if not text:
            i += 1
            continue

        if '日期分割线' in text or '置顶分割线' in text:
            i += 1
            continue

        if re.match(r'\d{4}\.\d{1,2}\.\d{1,2}', text):
            i += 1
            continue

        if text.startswith('【') or text.startswith('-'):
            i += 1
            continue

        is_skip = any(text.startswith(p) for p in SKIP_PREFIXES)
        if is_skip:
            i += 1
            continue

        has_skip_kw = any(kw in text for kw in SKIP_KEYWORDS)
        if has_skip_kw:
            i += 1
            continue

        if len(text) < 4:
            i += 1
            continue

        name = text
        i += 1

        while i < len(all_texts):
            next_text = all_texts[i].strip()
            if (next_text.startswith('.') or
                next_text.startswith('更') or
                next_text.startswith('第') or
                next_text.startswith('第二') or
                next_text.startswith('第三') or
                next_text.startswith('第四') or
                next_text.startswith('第五') or
                next_text.startswith('第六') or
                next_text.startswith('第七') or
                next_text.startswith('第八') or
                next_text.startswith('第九') or
                next_text.startswith('第十')):
                name += next_text
                i += 1
            else:
                break

        baidu_link = ''
        baidu_code = ''
        quark_link = ''
        k4_link = ''

        while i < len(all_texts):
            line = all_texts[i].strip()

            if '百度链接' in line or line == '百度':
                i += 1
                if i < len(all_texts):
                    link_line = all_texts[i].strip()
                    if link_line == '链接:' or link_line == '链接：':
                        i += 1
                        if i < len(all_texts):
                            baidu_link = all_texts[i].strip()
                    elif link_line.startswith('http'):
                        baidu_link = link_line
                i += 1
            elif '提取码' in line:
                m = re.search(r'提取码[：:]\s*(\S+)', line)
                if m:
                    baidu_code = m.group(1)
                else:
                    i += 1
                    if i < len(all_texts):
                        baidu_code = all_texts[i].strip().strip('：:')
                i += 1
            elif '夸克' in line:
                i += 1
                if i < len(all_texts) and '链接' in all_texts[i]:
                    i += 1
                if i < len(all_texts):
                    quark_link = all_texts[i].strip()
                    if not quark_link.startswith('http'):
                        quark_link = ''
                        i -= 1
                i += 1
            elif '4K链接' in line:
                i += 1
                if i < len(all_texts):
                    k4_link = all_texts[i].strip()
                    if not k4_link.startswith('http'):
                        k4_link = ''
                        i -= 1
                i += 1
            else:
                if (not line or
                    line.startswith('http') or
                    line.startswith('百度') or
                    line.startswith('夸克') or
                    line.startswith('提取码') or
                    line.startswith('4K') or
                    line.startswith('链接') or
                    line.startswith('迅雷') or
                    line.startswith('磁力') or
                    line.startswith('【')):
                    i += 1
                    continue

                if (len(line) > 3 and
                    not line.startswith('-') and
                    not any(line.startswith(p) for p in SKIP_PREFIXES) and
                    not '日期分割线' in line and
                    not '置顶分割线' in line):
                    break
                i += 1

        entries.append({
            'name': name.strip(),
            'baidu_link': baidu_link,
            'baidu_code': baidu_code,
            'quark_link': quark_link,
            '4k_link': k4_link,
            'update_time': crawl_time,
        })

    return entries


# ============================================================
#  API 请求 (需要从浏览器获取参数后使用)
# ============================================================

def fetch_doc(conn_id, user_group, file_version, csrf_token):
    """用预获取的参数请求文档数据"""
    session = requests.Session()
    session.headers.update({'User-Agent': UA})

    session.post(
        f'https://www.kdocs.cn/api/v3/office/session/{SHARE_CODE}/otl?first',
        headers={
            'content-type': 'text/plain;charset=UTF-8',
            'x-csrf-rand': csrf_token,
            'origin': 'https://www.kdocs.cn',
            'referer': SHARE_URL,
        },
        json={
            'token': '', 'group': user_group, 'connid': conn_id,
            'fileid': FILE_ID, 'front_ver': file_version,
            'endpoint_id': '', 'args': {'auto_slim': True},
        },
        timeout=15,
    )

    resp = session.post(
        f'https://www.kdocs.cn/api/v3/office/file/{SHARE_CODE}/open/otl',
        headers={
            'content-type': 'text/plain;charset=UTF-8',
            'x-csrf-rand': csrf_token,
            'origin': 'https://www.kdocs.cn',
            'referer': SHARE_URL,
        },
        json={
            'connid': conn_id,
            'args': {'password': '', 'readonly': False, 'modifyPassword': '',
                     'sync': True, 'startVersion': 0, 'endVersion': 0, 'autoSlim': True},
            'ex_args': {'queryInitArgs': {'enableCopyComments': False, 'checkAuditRule': False}},
            'group': user_group,
            'front_ver': file_version,
        },
        timeout=30,
    )
    return resp.json()


# ============================================================
#  一次性运行
# ============================================================

def run_once():
    """从本地 kdocs_raw_data.json 解析（先用浏览器抓取一次）"""
    now = datetime.now().strftime('%m月%d日 %H:%M')

    raw_path = os.path.join(SAVE_DIR, 'kdocs_raw_data.json')
    if not os.path.exists(raw_path):
        print('[错误] 找不到 kdocs_raw_data.json')
        print('请先通过浏览器获取文档数据并保存为此文件')
        return

    with open(raw_path, 'r', encoding='utf-8') as f:
        doc_data = json.load(f)

    entries = parse_doc(doc_data, now)

    output_path = os.path.join(SAVE_DIR, 'kdocs_result.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f'[{now}] 爬取完成，共 {len(entries)} 条')
    print(f'结果: {output_path}')

    for e in entries[:5]:
        print(f'  [{e["update_time"]}] {e["name"]}')
    if len(entries) > 5:
        print(f'  ... 等共 {len(entries)} 条')

    return entries


# ============================================================
#  监控模式 - 每15分钟循环
# ============================================================

def monitor(raw_path, interval_minutes=15):
    """监控模式：每隔 interval_minutes 分钟重新解析一次"""
    print(f'启动监控模式，每 {interval_minutes} 分钟爬取一次')
    print(f'按 Ctrl+C 停止\n')

    while True:
        try:
            now = datetime.now().strftime('%m月%d日 %H:%M')
            print(f'\n{"=" * 50}')
            print(f'[{now}] 开始爬取...')

            if os.path.exists(raw_path):
                mtime = os.path.getmtime(raw_path)
                file_time = datetime.fromtimestamp(mtime).strftime('%m月%d日 %H:%M')
                print(f'  读取文件 (最新修改: {file_time})')

                with open(raw_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)

                entries = parse_doc(doc_data, now)

                output_path = os.path.join(SAVE_DIR, 'kdocs_result.json')
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)

                print(f'  完成！共 {len(entries)} 条 -> {output_path}')
            else:
                print(f'  [警告] 文件不存在: {raw_path}')
                print(f'  请先手动获取一次数据')

        except Exception as e:
            print(f'  [错误] {e}')

        print(f'  下次爬取: {interval_minutes} 分钟后...')
        time.sleep(interval_minutes * 60)


# ============================================================
#  主入口
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='金山文档爬虫')
    parser.add_argument('--watch', '-w', action='store_true',
                        help='监控模式，每15分钟循环爬取')
    parser.add_argument('--interval', '-i', type=int, default=15,
                        help='监控间隔(分钟)，默认15')
    parser.add_argument('--file', '-f', type=str,
                        default=os.path.join(SAVE_DIR, 'kdocs_raw_data.json'),
                        help='原始JSON数据文件路径')
    parser.add_argument('--once', '-o', action='store_true',
                        help='只运行一次（默认）')

    args = parser.parse_args()

    if args.watch:
        monitor(args.file, args.interval)
    else:
        run_once()