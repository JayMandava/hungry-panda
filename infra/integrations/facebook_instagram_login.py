"""
Facebook Instagram Login Integration
Handles Facebook Login for Business → Page → Instagram Business Account resolution
"""
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from infra.config.settings import config
from infra.config.logging_config import logger


class FacebookInstagramAuthError(Exception):
    """Raised when Facebook Instagram auth fails"""
    pass


class FacebookInstagramAuthClient:
    """
    Client for Facebook Login for Business → Instagram Business Account flow
    
    Flow:
    1. User clicks Connect → redirect to Facebook dialog/oauth
    2. User authenticates → Meta redirects to callback with token in fragment
    3. Browser parses fragment → POST to finalize endpoint
    4. Backend resolves /me/accounts → Page → instagram_business_account
    5. Persist tokens and account IDs
    """
    
    API_VERSION = "v18.0"
    DIALOG_URL = "https://www.facebook.com/dialog/oauth"
    GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"
    
    # Required scopes for Instagram publishing via Facebook Login
    # Must exactly match Meta dashboard registered permissions:
    # instagram_basic, instagram_content_publish, pages_read_engagement,
    # business_management, pages_show_list
    REQUIRED_SCOPES = [
        "instagram_basic",
        "instagram_content_publish",
        "pages_read_engagement",
        "business_management",
        "pages_show_list",
    ]
    
    def __init__(self):
        self.app_id = config.FACEBOOK_APP_ID or config.INSTAGRAM_APP_ID
        self.app_secret = config.FACEBOOK_APP_SECRET or config.INSTAGRAM_APP_SECRET
        self.redirect_uri = config.FACEBOOK_INSTAGRAM_REDIRECT_URI or config.INSTAGRAM_REDIRECT_URI
        
        if not self.app_id or not self.app_secret:
            raise FacebookInstagramAuthError("Facebook App ID and Secret must be configured")
    
    def build_login_url(self, state: str = "") -> str:
        """
        Build Facebook Login dialog URL with Instagram onboarding extras
        
        Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login
        """
        if not self.redirect_uri:
            raise FacebookInstagramAuthError("Redirect URI not configured")
        
        # Ensure HTTPS
        if not self.redirect_uri.startswith("https://"):
            logger.warning(f"Redirect URI should use HTTPS: {self.redirect_uri}")
        
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "token",
            "scope": ",".join(self.REQUIRED_SCOPES),
            "display": "page",
            "extras": '{"setup":{"channel":"IG_API_ONBOARDING"}}',
        }
        
        if state:
            params["state"] = state
        
        return f"{self.DIALOG_URL}?{urlencode(params)}"
    
    def exchange_for_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """Exchange short-lived token for long-lived token"""
        url = f"{self.GRAPH_URL}/oauth/access_token"
        
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "fb_exchange_token": short_lived_token,
        }
        
        response = requests.get(url, params=params, timeout=30)
        result = self._parse_response(response)
        
        return {
            "access_token": result.get("access_token"),
            "expires_in": result.get("expires_in"),
            "token_type": result.get("token_type", "bearer"),
        }
    
    def get_pages(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get Pages for this user via /me/accounts
        Returns list of pages with connected Instagram business accounts
        """
        url = f"{self.GRAPH_URL}/me/accounts"
        
        params = {
            "access_token": access_token,
            "fields": "id,name,access_token,instagram_business_account",
        }
        
        response = requests.get(url, params=params, timeout=30)
        result = self._parse_response(response)
        
        pages = result.get("data", [])
        
        # Filter to pages with Instagram business accounts
        valid_pages = []
        for page in pages:
            if page.get("instagram_business_account"):
                valid_pages.append({
                    "id": page["id"],
                    "name": page["name"],
                    "access_token": page.get("access_token"),
                    "instagram_business_account_id": page["instagram_business_account"].get("id"),
                })
        
        return valid_pages
    
    def get_page_instagram_account(self, page_id: str, page_access_token: str) -> Optional[str]:
        """
        Get Instagram Business Account ID connected to a Page
        """
        url = f"{self.GRAPH_URL}/{page_id}"
        
        params = {
            "access_token": page_access_token,
            "fields": "instagram_business_account",
        }
        
        response = requests.get(url, params=params, timeout=30)
        result = self._parse_response(response)
        
        ig_account = result.get("instagram_business_account")
        if ig_account:
            return ig_account.get("id")
        
        return None
    
    def test_connection(self, instagram_business_account_id: str, access_token: str) -> bool:
        """
        Test that we can access the Instagram Business Account
        """
        url = f"{self.GRAPH_URL}/{instagram_business_account_id}"
        
        params = {
            "access_token": access_token,
            "fields": "id,username",
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            result = self._parse_response(response)
            return bool(result.get("id"))
        except FacebookInstagramAuthError:
            return False
    
    def publish_reel(
        self,
        instagram_business_account_id: str,
        access_token: str,
        video_url: str,
        caption: str,
        share_to_feed: bool = False,
    ) -> Dict[str, Any]:
        """
        Publish a Reel to Instagram using Facebook Login auth flow.
        
        Uses graph.facebook.com endpoints (not graph.instagram.com).
        """
        import time
        
        # Step 1: Create media container
        media_url = f"{self.GRAPH_URL}/{instagram_business_account_id}/media"
        
        media_params = {
            "access_token": access_token,
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        
        response = requests.post(media_url, params=media_params, timeout=30)
        media_result = self._parse_response(response)
        
        creation_id = media_result.get("id")
        if not creation_id:
            raise FacebookInstagramAuthError(
                f"Failed to create media container: {media_result}"
            )
        
        # Step 2: Wait for processing (Instagram requires this)
        max_wait = 60  # seconds
        wait_interval = 2  # seconds
        elapsed = 0
        
        status_url = f"{self.GRAPH_URL}/{creation_id}"
        
        final_status = ""
        while elapsed < max_wait:
            time.sleep(wait_interval)
            elapsed += wait_interval
            
            status_response = requests.get(
                status_url,
                params={"access_token": access_token, "fields": "status_code"},
                timeout=30
            )
            status_result = self._parse_response(status_response)
            
            final_status = status_result.get("status_code", "")
            if final_status == "FINISHED":
                break
            elif final_status == "ERROR":
                raise FacebookInstagramAuthError(
                    f"Media processing failed: {status_result}"
                )
        
        # If we timed out without reaching FINISHED, fail with clear error
        if final_status != "FINISHED":
            raise FacebookInstagramAuthError(
                f"Media processing timeout: Video is still processing after {max_wait}s. "
                f"Last status: {final_status}. Try publishing again later."
            )
        
        # Step 3: Publish the media
        publish_url = f"{self.GRAPH_URL}/{instagram_business_account_id}/media_publish"
        
        publish_params = {
            "access_token": access_token,
            "creation_id": creation_id,
        }
        
        publish_response = requests.post(publish_url, params=publish_params, timeout=30)
        publish_result = self._parse_response(publish_response)
        
        return publish_result
    
    def publish_image(
        self,
        instagram_business_account_id: str,
        access_token: str,
        image_url: str,
        caption: str,
    ) -> Dict[str, Any]:
        """
        Publish a single image to Instagram using Facebook Login auth flow.
        
        Uses graph.facebook.com endpoints.
        """
        # Step 1: Create media container for image
        media_url = f"{self.GRAPH_URL}/{instagram_business_account_id}/media"
        
        media_params = {
            "access_token": access_token,
            "image_url": image_url,
            "caption": caption,
        }
        
        response = requests.post(media_url, params=media_params, timeout=30)
        media_result = self._parse_response(response)
        
        creation_id = media_result.get("id")
        if not creation_id:
            raise FacebookInstagramAuthError(
                f"Failed to create media container: {media_result}"
            )
        
        # Step 2: Publish the media (images don't require processing wait)
        publish_url = f"{self.GRAPH_URL}/{instagram_business_account_id}/media_publish"
        
        publish_params = {
            "access_token": access_token,
            "creation_id": creation_id,
        }
        
        publish_response = requests.post(publish_url, params=publish_params, timeout=30)
        publish_result = self._parse_response(publish_response)
        
        return publish_result
    
    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse API response and handle errors"""
        try:
            data = response.json()
        except ValueError as e:
            raise FacebookInstagramAuthError(
                f"Invalid JSON response ({response.status_code}): {response.text[:200]}"
            ) from e
        
        if not response.ok:
            error = data.get("error", {})
            message = error.get("message", "Unknown error")
            code = error.get("code", "unknown")
            raise FacebookInstagramAuthError(f"Facebook API error {code}: {message}")
        
        return data


def get_configured_redirect_uri() -> Optional[str]:
    """Get the configured HTTPS redirect URI for Facebook Instagram auth"""
    # Prefer the new config, fall back to legacy
    uri = config.FACEBOOK_INSTAGRAM_REDIRECT_URI or config.INSTAGRAM_REDIRECT_URI
    
    # Default to tailscale URL if available
    if not uri:
        # Check if we have a tailscale hostname
        try:
            import socket
            hostname = socket.gethostname()
            # Try to construct from known tailscale pattern
            uri = "https://jay.taile36e8a.ts.net/api/facebook-instagram/oauth/callback"
        except:
            pass
    
    return uri
