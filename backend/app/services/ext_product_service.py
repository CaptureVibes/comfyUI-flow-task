from __future__ import annotations

import re
from typing import Any


_CURRENCY_CODE_TO_SYMBOL = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CNY": "￥",
    "KRW": "₩",
    "INR": "₹",
    "AUD": "A$",
    "CAD": "C$",
    "HKD": "HK$",
    "SGD": "S$",
    "TWD": "NT$",
    "BRL": "R$",
    "RUB": "₽",
    "THB": "฿",
}


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != "" and value != [] and value != {}
    }


def _normalize_price(price: Any) -> dict | None:
    """归一化价格字段：value 用纯数字字符串，currency 用 ISO 代码（如 USD）。"""
    if not isinstance(price, dict):
        return price if price is not None else None

    raw_currency = (price.get("currency") or "").strip()
    raw_value = price.get("value")
    extracted = price.get("extracted_value")

    if extracted is None and isinstance(raw_value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", raw_value.replace(",", ""))
        if match:
            try:
                extracted = float(match.group(0))
            except ValueError:
                extracted = None

    # 归一化 currency 为符号：若传入的是 ISO 代码（如 USD），转成符号（$）
    currency_symbol = _CURRENCY_CODE_TO_SYMBOL.get(raw_currency.upper(), raw_currency)
    if not currency_symbol and isinstance(raw_value, str):
        for symbol in _CURRENCY_CODE_TO_SYMBOL.values():
            if symbol in raw_value:
                currency_symbol = symbol
                break

    if extracted is not None:
        try:
            value_str = f"{float(extracted):.2f}"
        except (TypeError, ValueError):
            value_str = str(extracted)
    elif isinstance(raw_value, str):
        cleaned = re.sub(r"[^0-9.\-]", "", raw_value.replace(",", ""))
        value_str = cleaned or raw_value
    else:
        value_str = "" if raw_value is None else str(raw_value)

    return {
        "value": value_str,
        "extracted_value": float(extracted) if extracted is not None else None,
        "currency": currency_symbol,
    }


def _dedupe_ext_products(products: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        key = str(
            product.get("link")
            or product.get("image")
            or product.get("thumbnail")
            or product.get("title")
            or ""
        ).strip()
        if not key:
            key = repr(sorted(product.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(product)
    return result


def build_ext_product_from_solo_product(product: dict) -> dict | None:
    """Convert one AI solo product with a matched search result into an external product payload."""
    if not isinstance(product, dict):
        return None

    matched_product = product.get("matched_product")
    matched = matched_product if isinstance(matched_product, dict) else {}
    if product.get("product_search_status") != "matched" and not matched:
        return None

    product_code = matched.get("product_code") or ""
    sku_code = matched.get("sku_code") or ""
    has_internal_code = bool(product_code) or bool(sku_code)
    link = "" if has_internal_code else (matched.get("link") or product.get("product_link") or "")

    payload = {
        "id": matched.get("id"),
        "position": matched.get("position"),
        "title": matched.get("title") or product.get("product_title"),
        "link": link,
        "source": matched.get("source") or product.get("product_source"),
        "thumbnail": matched.get("thumbnail") or product.get("product_thumbnail"),
        "image": matched.get("image") or product.get("product_image_url"),
        "price": _normalize_price(matched.get("price") or product.get("product_price")),
        "tier": matched.get("tier") or product.get("product_tier"),
        "tier_label": matched.get("tier_label") or product.get("product_tier_label"),
        "product_code": product_code,
        "sku_code": sku_code,
        "is_internal": bool(matched.get("is_internal")),
        "product_name": product.get("name"),
        "product_description": product.get("description"),
        "product_search_query": product.get("product_search_query"),
        "product_search_trace_id": product.get("product_search_trace_id"),
    }
    cleaned = _clean_payload(payload)
    return cleaned or None


def build_ext_products_from_solo_products(solo_products: list | None) -> list[dict]:
    if not isinstance(solo_products, list):
        return []
    products = [
        ext_product
        for product in solo_products
        if isinstance(product, dict)
        for ext_product in [build_ext_product_from_solo_product(product)]
        if ext_product
    ]
    return _dedupe_ext_products(products)


def enrich_shot_with_ext_products(shot: dict) -> dict:
    """Return a copy of a shot with ext_products derived from matched solo_products."""
    if not isinstance(shot, dict):
        return shot
    existing = shot.get("ext_products") if isinstance(shot.get("ext_products"), list) else []
    generated = build_ext_products_from_solo_products(shot.get("solo_products"))
    return {
        **shot,
        "ext_products": _dedupe_ext_products([*existing, *generated]),
    }


def enrich_shots_with_ext_products(shots: list | None) -> list:
    if not isinstance(shots, list):
        return []
    return [
        enrich_shot_with_ext_products(shot) if isinstance(shot, dict) else shot
        for shot in shots
    ]


def build_ext_products_from_shots(shots: list | None) -> list[dict]:
    if not isinstance(shots, list):
        return []
    products: list[dict] = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        existing = shot.get("ext_products")
        if isinstance(existing, list):
            products.extend([item for item in existing if isinstance(item, dict)])
        products.extend(build_ext_products_from_solo_products(shot.get("solo_products")))
    return _dedupe_ext_products(products)
