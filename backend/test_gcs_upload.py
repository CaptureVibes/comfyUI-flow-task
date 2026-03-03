"""
GCS JSON 文件上传脚本
"""

import json
from pathlib import Path

from google.cloud import storage


def main():
    # 设置必需的 scopes
    SCOPES = ["https://www.googleapis.com/auth/devstorage.full_control"]

    from google.auth import default
    credentials, _ = default(scopes=SCOPES)
    client = storage.Client(credentials=credentials)

    bucket = client.bucket("decom-objects")

    # source_path = Path(__file__).parent / "2026-03-03.json"
    #
    # with open(source_path, "r", encoding="utf-8") as f:
    #     data = json.load(f)
    #
    # blob = bucket.blob("jimeng/jobs/2026-03-03.json")
    # blob.upload_from_string(
    #     json.dumps(data, ensure_ascii=False, indent=2),
    #     content_type="application/json",
    # )
    #
    # print(f"✅ 上传成功: gs://decom-objects/jimeng/jobs/2026-03-03.json")

    # 验证上传
    verify(bucket)


def verify(bucket):
    """验证文件是否上传成功"""
    blob = bucket.blob("jimeng/jobs/2026-03-03.json")

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
    print(f"📄 内容预览: {json.dumps(data, indent=2, ensure_ascii=False)}...")


if __name__ == "__main__":
    main()
