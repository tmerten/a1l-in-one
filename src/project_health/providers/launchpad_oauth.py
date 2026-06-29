"""OAuth 1.0a helpers for Launchpad."""

from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Final
from urllib.parse import parse_qsl, quote

import httpx

LAUNCHPAD_WEB_ROOT: Final = "https://launchpad.net"
OAUTH_SIGNATURE_METHOD: Final = "PLAINTEXT"
REQUEST_ATTEMPTS: Final = 3


class LaunchpadOAuthError(RuntimeError):
    """Launchpad OAuth flow failed."""


@dataclass(frozen=True)
class LaunchpadOAuthCredentials:
    """Launchpad OAuth credentials for signed API requests."""

    consumer_key: str
    access_token: str
    access_token_secret: str


@dataclass(frozen=True)
class LaunchpadRequestToken:
    """Temporary request token awaiting user authorization."""

    token: str
    token_secret: str


def oauth_authorization_header(
    *,
    consumer_key: str,
    token: str | None = None,
    token_secret: str = "",
) -> str:
    """Build a Launchpad OAuth PLAINTEXT Authorization header."""
    params = {
        "oauth_consumer_key": consumer_key,
        "oauth_signature_method": OAUTH_SIGNATURE_METHOD,
        "oauth_signature": f"&{token_secret}",
    }
    if token:
        params["oauth_token"] = token
    return "OAuth " + ", ".join(
        f'{quote(key, safe="")}="{quote(value, safe="~")}"'
        for key, value in sorted(params.items())
    )


def signed_headers(credentials: LaunchpadOAuthCredentials) -> dict[str, str]:
    """Return HTTP headers for a signed Launchpad API request."""
    return {
        "Authorization": oauth_authorization_header(
            consumer_key=credentials.consumer_key,
            token=credentials.access_token,
            token_secret=credentials.access_token_secret,
        )
    }


def parse_oauth_token_response(body: str) -> dict[str, str]:
    """Parse a Launchpad OAuth form-encoded token response."""
    return dict(parse_qsl(body, keep_blank_values=True))


def request_token(consumer_key: str, client: httpx.Client | None = None) -> LaunchpadRequestToken:
    """Request a temporary Launchpad token for user authorization."""
    close_client = client is None
    http = client or httpx.Client(base_url=LAUNCHPAD_WEB_ROOT, timeout=60.0)
    try:
        response = _post_with_retries(
            http,
            "/+request-token",
            data={
                "oauth_consumer_key": consumer_key,
                "oauth_signature_method": OAUTH_SIGNATURE_METHOD,
                "oauth_signature": "&",
            },
            action="request Launchpad OAuth token",
        )
        data = parse_oauth_token_response(response.text)
    finally:
        if close_client:
            http.close()

    token = data.get("oauth_token")
    token_secret = data.get("oauth_token_secret")
    if not token or not token_secret:
        raise ValueError("Launchpad did not return an OAuth request token")
    return LaunchpadRequestToken(token=token, token_secret=token_secret)


def authorize_url(token: str) -> str:
    """Build the URL the user must visit to authorize a request token."""
    return f"{LAUNCHPAD_WEB_ROOT}/+authorize-token?oauth_token={quote(token, safe='')}"


def exchange_request_token(
    consumer_key: str,
    request: LaunchpadRequestToken,
    client: httpx.Client | None = None,
) -> LaunchpadOAuthCredentials:
    """Exchange an authorized request token for reusable access credentials."""
    close_client = client is None
    http = client or httpx.Client(base_url=LAUNCHPAD_WEB_ROOT, timeout=60.0)
    try:
        response = _post_with_retries(
            http,
            "/+access-token",
            data={
                "oauth_consumer_key": consumer_key,
                "oauth_token": request.token,
                "oauth_signature_method": OAUTH_SIGNATURE_METHOD,
                "oauth_signature": f"&{request.token_secret}",
            },
            action="exchange Launchpad OAuth token",
        )
        data = parse_oauth_token_response(response.text)
    finally:
        if close_client:
            http.close()

    access_token = data.get("oauth_token")
    access_token_secret = data.get("oauth_token_secret")
    if not access_token or not access_token_secret:
        raise ValueError("Launchpad did not return OAuth access credentials")
    return LaunchpadOAuthCredentials(
        consumer_key=consumer_key,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )


def _post_with_retries(
    client: httpx.Client,
    path: str,
    *,
    action: str,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            response = client.post(path, data=data, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise LaunchpadOAuthError(
                f"Could not {action}: Launchpad returned HTTP {status}"
            ) from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < REQUEST_ATTEMPTS:
                sleep(0.5 * attempt)

    raise LaunchpadOAuthError(f"Could not {action}: {last_error}") from last_error
