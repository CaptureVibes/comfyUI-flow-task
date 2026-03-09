"""
GCS JSON 文件上传脚本
"""

import json
from pathlib import Path

from google.cloud import storage


def main():
    client = storage.Client("ai-agent-461123")

    bucket = client.bucket("decom-objects")

    # source_path = Path(__file__).parent / "2026-03-04.json"
    #
    # with open(source_path, "r", encoding="utf-8") as f:
    #     data = json.load(f)
    #
    # blob = bucket.blob("jimeng/jobs/2026-03-04.json")
    # blob.upload_from_string(
    #     json.dumps(data, ensure_ascii=False, indent=2),
    #     content_type="application/json",
    # )
    #
    # print(f"✅ 上传成功: gs://decom-objects/jimeng/jobs/2026-03-04.json")

    # 验证上传
    verify(bucket)


def verify(bucket):
    """验证文件是否上传成功"""
    blob = bucket.blob("jimeng/jobs/2026-03-10.json")

    if not blob.exists():
        print("❌ 文件不存在")
        return

    print(f"📦 文件存在: {blob.name}")
    print(f"📏 大小: {blob.size} bytes")
    print(f"🕒 更新时间: {blob.updated}")
    print(f"🔗 公开 URL: {blob.public_url}")

    # 下载并打印内容
    content = blob.download_as_text()
    data = json.loads(content)
    print(f"📄 内容预览: {json.dumps(data, indent=2, ensure_ascii=False)}")

    # """下载视频文件到本地"""
    # file_path  = "jimeng/results/2026-03-05/001/video.mp4"
    # print("文件路径: ", file_path)
    # blob = bucket.blob(file_path)
    #
    # if not blob.exists():
    #     print("❌ 文件不存在")
    #     return
    #
    # print(f"📦 文件存在: {blob.name}")
    # print(f"📏 大小: {blob.size} bytes")
    # print(f"🕒 更新时间: {blob.updated}")
    # print(f"🔗 公开 URL: {blob.public_url}")
    #
    # # 下载视频到本地
    # local_path = Path(__file__).parent / "downloaded_video.mp4"
    # blob.download_to_filename(str(local_path))
    # print(f"✅ 下载成功: {local_path}")



if __name__ == "__main__":
    main()
