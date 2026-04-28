from __future__ import annotations

from typing import Any


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != "" and value != [] and value != {}
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

    payload = {
        "id": matched.get("id"),
        "position": matched.get("position"),
        "title": matched.get("title") or product.get("product_title"),
        "link": matched.get("link") or product.get("product_link"),
        "source": matched.get("source") or product.get("product_source"),
        "thumbnail": matched.get("thumbnail") or product.get("product_thumbnail"),
        "image": matched.get("image") or product.get("product_image_url"),
        "price": matched.get("price") or product.get("product_price"),
        "tier": matched.get("tier") or product.get("product_tier"),
        "tier_label": matched.get("tier_label") or product.get("product_tier_label"),
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
