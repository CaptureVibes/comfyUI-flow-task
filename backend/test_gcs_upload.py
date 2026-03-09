"""
测试脚本：将本地 video.mp4 上传到 GCS 结果路径
路径格式: jimeng/results/{DATE}/{VIDEO_ID}/video.mp4
"""

from pathlib import Path

from google.cloud import storage

# ── 手动修改这两个变量 ─────────────────────────────────────────
DATE = "2026-03-09"
VIDEO_ID = "2450a7fc-2d69-40d9-8b34-dc3273de9703"
# ─────────────────────────────────────────────────────────────

LOCAL_VIDEO = Path(__file__).parent / "video.mp4"


def main():
    if not LOCAL_VIDEO.exists():
        print(f"❌ 本地视频文件不存在: {LOCAL_VIDEO}")
        return

    client = storage.Client("ai-agent-461123")
    bucket = client.bucket("audio_test_112")

    gcs_path = f"jimeng/results/{DATE}/{VIDEO_ID}/video.mp4"
    blob = bucket.blob(gcs_path)

    print(f"⬆️  正在上传 {LOCAL_VIDEO} → gs://audio_test_112/{gcs_path}")
    blob.upload_from_filename(str(LOCAL_VIDEO), content_type="video/mp4")

    print(f"✅ 上传成功!")
    print(f"   GCS 路径: gs://audio_test_112/{gcs_path}")
    print(f"   文件大小: {blob.size} bytes")
    print(f"   公开 URL: {blob.public_url}")


if __name__ == "__main__":
    main()
