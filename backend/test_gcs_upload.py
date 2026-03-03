"""
GCS JSON 文件上传脚本
"""

import json
from pathlib import Path

from google.cloud import storage


def main():
    client = storage.Client()
    bucket = client.bucket("decom-objects")

    source_path = Path(__file__).parent / "2026-03-03.json"

    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    blob = bucket.blob("jimeng/jobs/2026-03-03.json")
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type="application/json",
    )

    print(f"✅ 上传成功: gs://decom-objects/jimeng/jobs/2026-03-03.json")


if __name__ == "__main__":
    main()
