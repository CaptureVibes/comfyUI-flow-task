"""
测试 TikTok playAddr 是否可访问，并可选下载为本地 mp4。

用法：
    cd backend
    uv run python scripts/test_tiktok_playaddr.py \
      --url 'https://v16-webapp-prime.tiktok.com/video/...' \
      --output /tmp/tiktok_test.mp4

只测可访问性，不落盘：
    uv run python scripts/test_tiktok_playaddr.py \
      --url 'https://v16-webapp-prime.tiktok.com/video/...' \
      --head-only
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

DEFAULT_PLAY_ADDR = (
    "https://v16-webapp-prime.tiktok.com/video/tos/useast2a/tos-useast2a-ve-0068c002/o0Luj8gPmIIihFHPAMA9RegOe4If5CCSEGWjzL/?a=1988&bti=ODszNWYuMDE6&ch=0&cr=3&dr=0&lr=all&cd=0%7C0%7C0%7C&cv=1&br=2036&bt=1018&cs=0&ds=6&ft=-Csk_mH1PD12N83z2d-Ux_52KY6e3wv25VcAp&mime_type=video_mp4&qs=0&rc=NWY7OGRpN2RmPDU0N2RkM0BpajQ5N285cjRxeTMzNzczM0AxX2AyYzAuX2AxMF41MjZiYSMucmNoMmRjYmdgLS1kMTZzcw%3D%3D&btag=e000b0000&expire=1773997498&l=20260318170448CFD38371501E9427AD73&ply_type=2&policy=2&signature=6c6038a7a025e66f0578d60002f75de2&tk=tt_chain_token"
)


DEFAULT_HEADERS = {
    "Referer": "https://www.tiktok.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


async def fetch_playaddr(url: str, output: Path | None, head_only: bool) -> None:
    timeout = httpx.Timeout(60.0, connect=20.0)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
        trust_env=False,
    ) as client:
        if head_only:
            response = await client.get(url)
            print("status:", response.status_code)
            print("final_url:", str(response.url))
            print("content_type:", response.headers.get("content-type"))
            print("content_length:", response.headers.get("content-length"))
            body = response.text[:500] if "text" in (response.headers.get("content-type") or "") else ""
            if body:
                print("body_preview:", body)
            return

        if output is None:
            raise ValueError("下载模式必须提供 --output")

        output.parent.mkdir(parents=True, exist_ok=True)
        async with client.stream("GET", url) as response:
            print("status:", response.status_code)
            print("final_url:", str(response.url))
            print("content_type:", response.headers.get("content-type"))
            print("content_length:", response.headers.get("content-length"))
            if response.status_code >= 400:
                body = await response.aread()
                preview = body[:1000].decode("utf-8", errors="ignore")
                print("error_body_preview:", preview)
                response.raise_for_status()

            total = 0
            with output.open("wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)

        print("saved_to:", str(output))
        print("bytes_written:", total)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test TikTok playAddr download with required headers.")
    parser.add_argument("--url", default=DEFAULT_PLAY_ADDR, help="TikTok video playAddr")
    parser.add_argument(
        "--output",
        default="tiktok_test.mp4",
        help="Output file path when downloading. Default: tiktok_test.mp4",
    )
    parser.add_argument(
        "--head-only",
        action="store_true",
        help="Only test accessibility and print response metadata, do not save file.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    output = None if args.head_only else Path(args.output).expanduser().resolve()
    try:
        await fetch_playaddr(args.url, output, args.head_only)
    except httpx.HTTPStatusError as exc:
        print("http_error_status:", exc.response.status_code)
        print("http_error_url:", str(exc.request.url))
        if exc.response is not None:
            await exc.response.aread()
        text = exc.response.text[:1000] if exc.response is not None else ""
        if text:
            print("http_error_body:", text)
        raise
    except Exception as exc:
        print("error:", repr(exc))
        raise


if __name__ == "__main__":
    asyncio.run(main())
