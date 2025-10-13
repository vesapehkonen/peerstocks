from config import settings
from fastapi import HTTPException
from opensearchpy import AuthenticationException, OpenSearch, TransportError

CONNECT_TIMEOUT = 3
READ_TIMEOUT = 7


def build_opensearch_client() -> OpenSearch:
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
        transport_options={"socket_keepalive": True},
    )
    return client


def run_opensearch_raw(client, index, query):
    try:
        resp = client.search(index=index, body=query, request_timeout=READ_TIMEOUT)
    except AuthenticationException as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc
    except TransportError as exc:
        status = getattr(exc, "status_code", 502) or 502
        details = getattr(exc, "error", None) or getattr(exc, "info", None) or str(exc)
        raise HTTPException(status_code=status, detail=f"OpenSearch error {status}: {details}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc
    return resp


def run_opensearch_query(client, index, query):
    resp = run_opensearch_raw(client, index, query)
    return resp.get("hits", {}).get("hits", [])
