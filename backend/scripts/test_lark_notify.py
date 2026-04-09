"""
测试 Lark 日报推送

用法：
    cd backend
    uv run python scripts/test_lark_notify.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from app.services.lark_notify_scheduler import _send_daily_report
    from app.core.config import settings

    if not settings.lark_webhook_url:
        print("❌ LARK_WEBHOOK_URL 未配置，请在 .env 中设置")
        return

    print(f"✅ Webhook: {settings.lark_webhook_url[:60]}...")
    print("📤 正在读取数据库并发送昨日日报...")
    await _send_daily_report()
    print("✅ 发送完成，请查看 Lark")


if __name__ == "__main__":
    asyncio.run(main())
