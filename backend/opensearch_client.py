"""
Same interface as the old httpx-based client, but implemented with opensearch-py.

- get_opensearch_client()    -> returns a handle (kept for compatibility; value is not used)
- run_opensearch_query(...)  -> returns resp["hits"]["hits"]
- run_opensearch_raw(...)    -> returns full JSON dict

TLS/auth behavior:
- If OPENSEARCH_URL is https:// and OS_CA_CERT is set, verify against that CA.
- If OPENSEARCH_URL is https:// and OS_VERIFY_SSL is falsey, disable verification and hostname checks.
- Otherwise, default verification applies.
"""

from fastapi import HTTPException
from config import settings

from typing import Optional, Dict, Any
from opensearchpy import OpenSearch, TransportError, AuthenticationException


def _as_bool(val, default=True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def _want_https() -> bool:
    return str(settings.OPENSEARCH_URL).strip().lower().startswith("https://")


def _build_os_client() -> OpenSearch:
    url = str(settings.OPENSEARCH_URL).strip()
    if not url:
        raise SystemExit("Set OPENSEARCH_URL (and optionally OS_USER/OS_PASS).")

    user = getattr(settings, "OS_USER", None)
    pwd  = getattr(settings, "OS_PASS", None)
    ca   = getattr(settings, "OS_CA_CERT", None)

    # TLS flags
    verify_certs = True
    ssl_assert_hostname = True
    ssl_show_warn = False
    kw: Dict[str, Any] = {
        "hosts": [url],  # full URL string is most robust
        "timeout": max(getattr(settings, "REQUEST_READ_TIMEOUT", 20), 1),
        "max_retries": 3,
        "retry_on_timeout": True,
    }

    if _want_https():
        if ca:
            kw["ca_certs"] = ca
            verify_certs = True
        else:
            verify_certs = _as_bool(getattr(settings, "OS_VERIFY_SSL", True), True)
            if not verify_certs:
                ssl_assert_hostname = False
                ssl_show_warn = False

    kw.update(
        dict(
            verify_certs=verify_certs,
            ssl_assert_hostname=ssl_assert_hostname,
            ssl_show_warn=ssl_show_warn,
        )
    )

    # Auth: prefer 3.x param, fall back to 2.x seamlessly
    if user and pwd:
        try:
            return OpenSearch(basic_auth=(user, pwd), **kw)
        except TypeError:
            return OpenSearch(http_auth=(user, pwd), **kw)
    return OpenSearch(**kw)


# Keep a module-level handle (matches old pattern)
# Note: callers might store this, so we return it from get_opensearch_client().
_os_client: Optional[OpenSearch] = _build_os_client()


def get_opensearch_client():
    """Kept for compatibility with existing call sites."""
    return _os_client


def _search_url(index: str) -> str:
    """Kept for compatibility with logs/tests that may inspect URLs."""
    base_url = str(settings.OPENSEARCH_URL).rstrip("/")
    return f"{base_url}/{index}/_search"


def run_opensearch_query(http_client, index: str, query: dict):
    """
    Same signature as before; http_client is ignored (kept for compatibility).
    Returns the list of hits like the old function did.
    """
    client = _os_client
    try:
        resp = client.search(
            index=index,
            body=query,
            request_timeout=getattr(settings, "REQUEST_READ_TIMEOUT", 20),
        )
    except AuthenticationException as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc
    except TransportError as exc:
        status = getattr(exc, "status_code", 502) or 502
        details = getattr(exc, "error", None) or getattr(exc, "info", None) or str(exc)
        raise HTTPException(status_code=status, detail=f"OpenSearch error {status}: {details}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc

    return resp.get("hits", {}).get("hits", [])


def run_opensearch_raw(http_client, index: str, query: dict):
    """
    Same signature as before; http_client is ignored.
    Returns the full JSON response dict like the old function did.
    """
    client = _os_client
    try:
        resp = client.search(
            index=index,
            body=query,
            request_timeout=getattr(settings, "REQUEST_READ_TIMEOUT", 20),
        )
    except AuthenticationException as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc
    except TransportError as exc:
        status = getattr(exc, "status_code", 502) or 502
        details = getattr(exc, "error", None) or getattr(exc, "info", None) or str(exc)
        raise HTTPException(status_code=status, detail=f"OpenSearch error {status}: {details}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc

    return resp
