"""
Instagram Login integration for Hungry Panda.

Implements the official Instagram Platform OAuth flow for professional accounts
using "Instagram API with Instagram Login".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from config.settings import config


DEFAULT_SCOPES = (
    "instagram_business_basic",
    "instagram_business_content_publish",
)


class InstagramLoginError(RuntimeError):
    """Raised when Instagram login or API calls fail."""


@dataclass
class InstagramLoginClient:
    """Minimal Instagram Platform client for OAuth and profile validation."""

    app_id: str
    app_secret: str
    redirect_uri: str
    api_version: str = "v25.0"

    @classmethod
    def from_redirect_uri(cls, redirect_uri: str) -> "InstagramLoginClient":
        if not config.INSTAGRAM_APP_ID or not config.INSTAGRAM_APP_SECRET:
            raise InstagramLoginError(
                "INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET must be configured."
            )

        return cls(
            app_id=config.INSTAGRAM_APP_ID,
            app_secret=config.INSTAGRAM_APP_SECRET,
            redirect_uri=redirect_uri,
            api_version=config.INSTAGRAM_API_VERSION,
        )

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(DEFAULT_SCOPES),
            "state": state,
            "enable_fb_login": "0",
            "force_reauth": "false",
        }
        return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, code: str) -> Dict[str, Any]:
        response = requests.post(
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
            timeout=30,
        )
        return self._parse_response(response)

    def exchange_for_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        response = requests.get(
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self.app_secret,
                "access_token": short_lived_token,
            },
            timeout=30,
        )
        return self._parse_response(response)

    def refresh_long_lived_token(self, access_token: str) -> Dict[str, Any]:
        response = requests.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": access_token,
            },
            timeout=30,
        )
        return self._parse_response(response)

    def get_profile(self, access_token: str) -> Dict[str, Any]:
        response = requests.get(
            f"https://graph.instagram.com/{self.api_version}/me",
            params={
                "fields": ",".join(
                    [
                        "user_id",
                        "username",
                        "name",
                        "account_type",
                        "profile_picture_url",
                        "followers_count",
                        "follows_count",
                        "media_count",
                    ]
                ),
                "access_token": access_token,
            },
            timeout=30,
        )
        return self._parse_response(response)

    def get_content_publishing_limit(
        self,
        user_id: str,
        access_token: str,
    ) -> Dict[str, Any]:
        response = requests.get(
            f"https://graph.instagram.com/{self.api_version}/{user_id}/content_publishing_limit",
            params={"access_token": access_token},
            timeout=30,
        )
        return self._parse_response(response)

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise InstagramLoginError(
                f"Instagram API returned non-JSON response ({response.status_code})."
            ) from exc

        if not response.ok:
            error = payload.get("error") or payload
            if isinstance(error, dict):
                message = error.get("message") or error.get("error_message") or str(error)
            else:
                message = str(error)
            raise InstagramLoginError(message)

        return self._unwrap_payload(payload)

    @staticmethod
    def _unwrap_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return first
        if isinstance(data, dict):
            return data
        return payload


def get_configured_redirect_uri(base_url: Optional[str] = None) -> str:
    """Return the OAuth redirect URI configured for the current deployment."""
    if config.INSTAGRAM_REDIRECT_URI:
        return config.INSTAGRAM_REDIRECT_URI

    if not base_url:
        raise InstagramLoginError(
            "INSTAGRAM_REDIRECT_URI is not configured and no request base URL was provided."
        )

    return f"{base_url.rstrip('/')}/api/instagram/oauth/callback"
