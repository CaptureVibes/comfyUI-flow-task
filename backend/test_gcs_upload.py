"""
测试脚本：将本地 video.mp4 上传到 GCS 结果路径
路径格式: jimeng/results/{DATE}/{VIDEO_ID}/video.mp4
"""

from pathlib import Path

from google.cloud import storage

# ── 手动修改这两个变量 ─────────────────────────────────────────
DATE = "2026-03-11"
VIDEO_ID = "95c3afc1-359b-4612-a353-8163d7a510f9"
PROD_BUCKET =  "decom-objects"
TEST_BUCKET =  "audio_test_112"
# ─────────────────────────────────────────────────────────────

LOCAL_VIDEO = Path(__file__).parent / "video.mp4"


def check_mp4_exists(date: str, video_id: str) -> bool:
    """检查指定路径的 MP4 文件是否存在"""
    client = storage.Client("ai-agent-461123")
    bucket = client.bucket(PROD_BUCKET)
    gcs_path = f"jimeng/results/{date}/{video_id}/video.mp4"
    blob = bucket.blob(gcs_path)
    return blob.exists()


def check_json_exists(): 
    if not LOCAL_VIDEO.exists():
        print(f"❌ 本地视频文件不存在: {LOCAL_VIDEO}")
        return

    client = storage.Client("ai-agent-461123")
    bucket = client.bucket(TEST_BUCKET)

    gcs_path = f"jimeng/results/{DATE}/{VIDEO_ID}/video.mp4"
    blob = bucket.blob(gcs_path)

    print(f"⬆️  正在上传 {LOCAL_VIDEO} → gs://audio_test_112/{gcs_path}")
    blob.upload_from_filename(str(LOCAL_VIDEO), content_type="video/mp4")

    print(f"✅ 上传成功!")
    print(f"   GCS 路径: gs://audio_test_112/{gcs_path}")
    print(f"   文件大小: {blob.size} bytes")
    print(f"   公开 URL: {blob.public_url}")

def main():
    check_json_exists()


if __name__ == "__main__":
    main()
