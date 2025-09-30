#!/usr/bin/env python3
import json
from pathlib import Path

from config import settings
from opensearchpy import OpenSearch

DEFAULT_EARNINGS_INDEX = "earnings_data"
DEFAULT_PRICES_INDEX = "stock_prices"
DEFAULT_SUMMARY_INDEX = "stock_summary"
DEFAULT_METADATA_INDEX = "stock_metadata"

MAPPING_FILES = [
    "earnings_data.mapping.json",
    "stock_prices.mapping.json",
    "stock_summary.mapping.json",
    "stock_metadata.mapping.json",
]

CONNECT_TIMEOUT = 3


def os_client() -> OpenSearch:
    auth = None
    if settings.OS_USER and settings.OS_PASS:
        auth = (settings.OS_USER, settings.OS_PASS.get_secret_value())
    client = OpenSearch(
        hosts=[str(settings.OS_HOST)],
        http_auth=auth,
        timeout=CONNECT_TIMEOUT,
        max_retries=3,
        retry_on_timeout=True,
        verify_certs=False,
        ssl_show_warn=False,
    )
    return client


def load_mapping_file(path: Path):
    """
    Returns (index_name, mappings_block)
    where mappings_block is the value of the top-level '<index_name>': {'mappings': {...}}
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or len(data) != 1:
        raise ValueError(f"{path.name}: expected a single top-level key with index name.")

    index_name, idx_payload = next(iter(data.items()))
    if not isinstance(idx_payload, dict) or "mappings" not in idx_payload:
        raise ValueError(f"{path.name}: expected object with a 'mappings' key.")

    mappings = idx_payload["mappings"]
    if not isinstance(mappings, dict):
        raise ValueError(f"{path.name}: 'mappings' must be an object.")

    return index_name, mappings


def ensure_index_with_mapping(client: OpenSearch, index_name: str, mappings: dict):
    """
    Create index with the provided mappings if it doesn't exist.
    Non-destructive: if index exists, we do not modify it.
    """
    if client.indices.exists(index=index_name):
        print(f"[SKIP] Index '{index_name}' already exists.")
        return

    body = {"mappings": mappings}
    print(f"[CREATE] Index '{index_name}' …")
    client.indices.create(index=index_name, body=body)
    print(f"[OK] Created '{index_name}'")


def main():
    print("[INIT] Starting index initialization …")

    here = Path(__file__).resolve().parent
    client = os_client()

    print("[MAPPINGS] Applying local mapping files:")
    for fname in MAPPING_FILES:
        path = here / fname
        if not path.exists():
            raise SystemExit(f"Missing mapping file: {fname} (expected in {here})")

        index_name, mappings = load_mapping_file(path)
        print(f"  - {fname} -> '{index_name}'")
        ensure_index_with_mapping(client, index_name, mappings)

    # Sanity ping
    try:
        info = client.info()
        cluster = info.get("cluster_name") or info.get("cluster_uuid") or "unknown-cluster"
        print(f"[DONE] Indices initialized. Cluster: {cluster}")
    except Exception:
        print("[DONE] Indices initialized.")


if __name__ == "__main__":
    main()
