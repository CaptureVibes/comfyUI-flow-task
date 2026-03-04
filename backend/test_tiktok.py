import json

import yt_dlp

url = "https://www.tiktok.com/@imsytwjzu7/video/7612595498301525262"

# ✅ 获取视频信息 + 文案（不下载）
with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
    info = ydl.extract_info(url, download=False)

    # 基础信息
    print("=" * 50)
    print("视频标题:", info.get('title'))
    print("文案:", info.get('description'))
    print("作者:", info.get('uploader'))
    print("作者ID:", info.get('uploader_id'))

    # 互动数据
    print("=" * 50)
    print("点赞数:", info.get('like_count', 'N/A'))
    print("播放数:", info.get('view_count', 'N/A'))
    print("评论数:", info.get('comment_count', 'N/A'))
    print("转发数:", info.get('repost_count', 'N/A'))

    # 视频直链（可直接用 requests 下载）
    print("=" * 50)
    print("视频直链:", info.get('url'))

    # 完整数据（调试用）
    print("Result:", json.dumps(info, indent=2, ensure_ascii=False))

# ✅ 直接下载视频到本地
ydl_opts = {
    'outtmpl': 'video.%(ext)s',  # 保存为 video.mp4
    'format': 'best',             # 最高画质
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])