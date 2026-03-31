"""
GCS 目录迁移脚本：将 decom-objects/jimeng/results/2026-03-30/ 下的所有文件复制到 2026-03-31/
"""

from google.cloud import storage

# ── 配置 ─────────────────────────────────────────────────────────
PROJECT_ID = "ai-agent-461123"
BUCKET_NAME = "decom-objects"
SRC_PREFIX = "jimeng/results/2026-03-30/"
DST_PREFIX = "jimeng/results/2026-03-31/"
# ─────────────────────────────────────────────────────────────────


def main():
    client = storage.Client(PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    blobs = list(bucket.list_blobs(prefix=SRC_PREFIX))
    if not blobs:
        print(f"源目录为空: gs://{BUCKET_NAME}/{SRC_PREFIX}")
        return

    print(f"找到 {len(blobs)} 个文件，开始复制...")

    for i, blob in enumerate(blobs, 1):
        # 跳过"目录"占位符（GCS 有时会返回 size=0 的目录标记）
        if blob.name.endswith("/") and blob.size == 0:
            continue

        dst_name = blob.name.replace(SRC_PREFIX, DST_PREFIX, 1)
        dst_blob = bucket.blob(dst_name)
        dst_blob.upload_from_string(
            blob.download_as_bytes(),
            content_type=blob.content_type or "application/octet-stream",
        )
        print(f"  [{i}/{len(blobs)}] {blob.name} → {dst_name}")

    print(f"\n✅ 完成，共复制 {len(blobs)} 个文件")
    print(f"   目标: gs://{BUCKET_NAME}/{DST_PREFIX}")


if __name__ == "__main__":
    main()
