"""
LinkedIn Client

Client for interacting with LinkedIn via the unofficial linkedin-api library.
Supports profile lookups, searches, messaging, and connection management.

Authentication:
    1. Username/password login (may trigger 2FA/challenge)
    2. Browser cookies (li_at, JSESSIONID) from Brave/Chrome/Firefox/Edge
    3. Environment variables (LINKEDIN_LI_AT, LINKEDIN_JSESSIONID)

IMPORTANT: This uses an unofficial API. Be conservative with rate limits
to avoid account restrictions.
"""

import os
import sys
import json
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple

from requests.cookies import RequestsCookieJar

logger = logging.getLogger(__name__)

# Lazy imports for linkedin-api (may not be installed)
Linkedin = None
generate_trackingId_as_charString = None
browser_cookie3 = None


def _ensure_imports():
    """Lazily import linkedin-api dependencies."""
    global Linkedin, generate_trackingId_as_charString, browser_cookie3
    
    if Linkedin is None:
        try:
            from linkedin_api import Linkedin as _Linkedin
            from linkedin_api.linkedin import generate_trackingId_as_charString as _gen_tracking
            Linkedin = _Linkedin
            generate_trackingId_as_charString = _gen_tracking
        except ImportError:
            raise ImportError(
                "linkedin-api library not installed. "
                "Install with: pip install linkedin-api"
            )
    
    if browser_cookie3 is None:
        try:
            import browser_cookie3 as _bc3
            browser_cookie3 = _bc3
        except ImportError:
            logger.warning("browser_cookie3 not installed - browser cookie auth unavailable")


class LinkedInMessageError(Exception):
    """Custom exception for LinkedIn messaging errors."""
    pass


class LinkedInAuthError(Exception):
    """Custom exception for LinkedIn authentication errors."""
    pass


class LinkedInClient:
    """
    Client wrapper for LinkedIn API operations.
    
    Handles authentication and provides clean methods for common operations.
    """
    
    def __init__(self, client):
        """
        Initialize with an authenticated linkedin-api client.
        
        Args:
            client: Authenticated Linkedin client instance
        """
        self._client = client
        self._my_profile = None
    
    # ============ Profile Operations ============
    
    def get_profile(
        self,
        public_id: Optional[str] = None,
        urn_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a LinkedIn profile.
        
        Args:
            public_id: Public profile ID (e.g., "john-doe-123456")
            urn_id: URN ID (e.g., "ACoAABxxxx")
            
        Returns:
            Profile data dictionary
            
        Raises:
            ValueError: If profile not found or API returns error
        """
        if not public_id and not urn_id:
            raise ValueError("Must provide either public_id or urn_id")
        
        result = self._client.get_profile(public_id=public_id, urn_id=urn_id)
        
        # Check if API returned an error response
        if isinstance(result, dict):
            if "message" in result and "status" in result:
                # API error response
                raise ValueError(f"LinkedIn API error: {result.get('message', 'Unknown error')}")
            if not result:
                raise ValueError("Profile not found or empty response")
        
        return result
    
    def get_profile_contact_info(
        self,
        public_id: Optional[str] = None,
        urn_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get contact info for a profile (email, phone, etc. if available).
        
        Args:
            public_id: Public profile ID
            urn_id: URN ID
            
        Returns:
            Contact info dictionary
        """
        if not public_id and not urn_id:
            raise ValueError("Must provide either public_id or urn_id")
        
        return self._client.get_profile_contact_info(
            public_id=public_id,
            urn_id=urn_id
        )
    
    def get_my_profile(self) -> Dict[str, Any]:
        """
        Get the authenticated user's own profile.
        
        Returns:
            Own profile data (normalized structure)
        """
        if self._my_profile is None:
            raw_profile = self._client.get_user_profile()
            # Normalize the profile structure
            # get_user_profile() returns a different format than get_profile()
            self._my_profile = raw_profile
            
            # Extract mini profile data if present
            if "miniProfile" in raw_profile:
                mini = raw_profile["miniProfile"]
                # Merge mini profile fields into top level for consistency
                for key in ["firstName", "lastName", "publicIdentifier", "entityUrn", "occupation"]:
                    if key in mini and key not in self._my_profile:
                        self._my_profile[key] = mini[key]
                # Map occupation to headline
                if "occupation" in mini and "headline" not in self._my_profile:
                    self._my_profile["headline"] = mini["occupation"]
            
        return self._my_profile
    
    def get_my_urn(self) -> Optional[str]:
        """
        Get the authenticated user's URN ID.
        
        Returns:
            URN ID string or None
        """
        profile = self.get_my_profile()
        
        # Try different places where URN might be
        urn = profile.get("entityUrn") or profile.get("urn_id")
        if not urn and "miniProfile" in profile:
            urn = profile["miniProfile"].get("entityUrn")
        
        # Extract just the ID part if it's a full URN
        if urn and ":" in urn:
            urn = urn.split(":")[-1]
        
        return urn
    
    # ============ Connection Operations ============
    
    def get_connections(
        self,
        urn_id: Optional[str] = None,
        limit: int = -1
    ) -> List[Dict[str, Any]]:
        """
        Get connections for a profile.
        
        Args:
            urn_id: Profile URN ID (defaults to own profile)
            limit: Maximum connections to return (-1 for all)
            
        Returns:
            List of connection profiles
        """
        # If no URN provided, get the authenticated user's URN
        if not urn_id:
            urn_id = self.get_my_urn()
            if not urn_id:
                raise ValueError("Could not determine your profile URN. Please provide urn_id explicitly.")
        
        return self._client.get_profile_connections(urn_id=urn_id)
    
    # ============ Search Operations ============
    
    def search_people(
        self,
        keywords: Optional[str] = None,
        network_depths: Optional[List[str]] = None,
        current_company: Optional[List[str]] = None,
        past_company: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for people on LinkedIn.
        
        Args:
            keywords: Search keywords
            network_depths: List of network depths ("F" = 1st, "S" = 2nd, "O" = 3rd+)
            current_company: List of current company IDs
            past_company: List of past company IDs
            industries: List of industry IDs
            regions: List of region IDs
            limit: Maximum results to return
            
        Returns:
            List of matching profiles
        """
        return self._client.search_people(
            keywords=keywords,
            network_depths=network_depths,
            current_company=current_company,
            past_companies=past_company,
            industries=industries,
            regions=regions,
            limit=limit
        )
    
    # ============ Messaging Operations ============
    
    def get_conversations(self) -> List[Dict[str, Any]]:
        """
        Get all conversations.
        
        Returns:
            List of conversation objects
        """
        result = self._client.get_conversations()
        
        # The API returns a dict with 'elements' key containing the conversations
        if isinstance(result, dict):
            return result.get("elements", [])
        elif isinstance(result, list):
            return result
        else:
            return []
    
    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get messages from a specific conversation.
        
        Args:
            conversation_id: The conversation URN ID
            
        Returns:
            Conversation with messages
        """
        return self._client.get_conversation(conversation_id)
    
    def get_conversation_details(self, profile_urn: str) -> Dict[str, Any]:
        """
        Get conversation details with a specific profile.
        
        Args:
            profile_urn: The profile URN ID
            
        Returns:
            Conversation details
        """
        return self._client.get_conversation_details(profile_urn)
    
    def send_message(
        self,
        message_body: str,
        conversation_urn_id: Optional[str] = None,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """
        Send a message.
        
        Args:
            message_body: The message text to send
            conversation_urn_id: Existing conversation URN ID (for replies)
            recipients: List of profile URN IDs (for new conversations)
            
        Returns:
            True if message was sent successfully
            
        Raises:
            LinkedInMessageError: If the message fails to send
        """
        _ensure_imports()
        
        if not conversation_urn_id and not recipients:
            raise LinkedInMessageError("Must provide conversation_urn_id or recipients")
        
        params = {"action": "create"}
        
        message_event = {
            "eventCreate": {
                "originToken": str(uuid.uuid4()),
                "value": {
                    "com.linkedin.voyager.messaging.create.MessageCreate": {
                        "attributedBody": {
                            "text": message_body,
                            "attributes": [],
                        },
                        "attachments": [],
                    }
                },
                "trackingId": generate_trackingId_as_charString(),
            },
            "dedupeByClientGeneratedToken": False,
        }
        
        if conversation_urn_id and not recipients:
            res = self._client._post(
                f"/messaging/conversations/{conversation_urn_id}/events",
                params=params,
                data=json.dumps(message_event),
            )
        elif recipients and not conversation_urn_id:
            message_event["recipients"] = recipients
            message_event["subtype"] = "MEMBER_TO_MEMBER"
            payload = {
                "keyVersion": "LEGACY_INBOX",
                "conversationCreate": message_event,
            }
            res = self._client._post(
                f"/messaging/conversations",
                params=params,
                data=json.dumps(payload),
            )
        else:
            raise LinkedInMessageError("Provide either conversation_urn_id OR recipients, not both")
        
        if res.status_code != 201:
            error_message = f"LinkedIn API error (Status {res.status_code})"
            try:
                error_detail = res.json()
                error_message += f": {error_detail}"
            except:
                error_message += f": {res.text}"
            raise LinkedInMessageError(error_message)
        
        return True


def _load_cookies_from_browsers() -> Optional[RequestsCookieJar]:
    """
    Try to load LinkedIn cookies from various browsers.
    
    Returns:
        RequestsCookieJar if successful, None otherwise
    """
    _ensure_imports()
    
    if browser_cookie3 is None:
        return None
    
    browser_methods = [
        browser_cookie3.brave,
        browser_cookie3.chrome,
        browser_cookie3.firefox,
        browser_cookie3.edge,
    ]
    
    for browser_method in browser_methods:
        try:
            cj = browser_method(domain_name='linkedin.com')
            
            has_li_at = any(cookie.name == "li_at" for cookie in cj)
            has_jsessionid = any(cookie.name.lower() == "jsessionid" for cookie in cj)
            
            if has_li_at and has_jsessionid:
                logger.info(f"Loaded LinkedIn cookies from {browser_method.__name__}")
                return cj
            else:
                logger.debug(f"Missing cookies in {browser_method.__name__}")
        except Exception as e:
            logger.debug(f"Failed to load cookies from {browser_method.__name__}: {e}")
    
    return None


def _load_cookies_from_env() -> Optional[RequestsCookieJar]:
    """
    Load LinkedIn cookies from environment variables.
    
    Expected variables:
        LINKEDIN_LI_AT: The li_at cookie value
        LINKEDIN_JSESSIONID: The JSESSIONID cookie value
    
    Returns:
        RequestsCookieJar if successful, None otherwise
    """
    li_at = os.getenv("LINKEDIN_LI_AT")
    jsession = os.getenv("LINKEDIN_JSESSIONID")
    
    if not li_at or not jsession:
        return None
    
    # Clean up li_at - remove any surrounding quotes
    li_at = li_at.strip().strip('"').strip("'")
    
    # JSESSIONID must have quotes around it for LinkedIn API
    # Format should be: "ajax:1234567890123456789"
    jsession = jsession.strip()
    
    # Remove outer quotes if present (env files can add extra escaping)
    if (jsession.startswith('"\\"') and jsession.endswith('\\""')) or \
       (jsession.startswith("'\\\"") and jsession.endswith("\\\"'")):
        # Handle escaped quotes: "\"ajax:...\"" -> "ajax:..."
        jsession = jsession[2:-2]
    elif (jsession.startswith('"') and jsession.endswith('"') and jsession.count('"') == 2):
        # Already properly quoted: "ajax:..." -> keep as is
        pass
    elif jsession.startswith("'") and jsession.endswith("'"):
        # Single quoted in env: 'ajax:...' or '"ajax:..."'
        jsession = jsession[1:-1]
    
    # Now ensure it has the required quotes
    if not jsession.startswith('"'):
        jsession = '"' + jsession
    if not jsession.endswith('"'):
        jsession = jsession + '"'
    
    # Validate cookie formats
    if not li_at.startswith("AQ"):
        logger.warning(f"li_at cookie doesn't start with 'AQ' - may be invalid")
    
    if not jsession.startswith('"ajax:'):
        logger.warning(f"JSESSIONID doesn't start with '\"ajax:' - may be invalid. Got: {jsession[:20]}...")
    
    logger.info(f"Loading cookies from env - li_at: {li_at[:10]}..., JSESSIONID: {jsession[:15]}...")
    
    cookie_jar = RequestsCookieJar()
    cookie_jar.set("li_at", li_at, domain=".linkedin.com", path="/")
    cookie_jar.set("JSESSIONID", jsession, domain=".linkedin.com", path="/")
    
    return cookie_jar


def _create_client_with_cookies(cookies: RequestsCookieJar) -> LinkedInClient:
    """Create a LinkedIn client using cookies."""
    _ensure_imports()
    
    client = Linkedin(
        username="",  # not needed with cookies
        password="",
        cookies=cookies
    )
    return LinkedInClient(client)


def _create_client_with_credentials(email: str, password: str) -> LinkedInClient:
    """Create a LinkedIn client using username/password."""
    _ensure_imports()
    
    client = Linkedin(
        email,
        password,
        refresh_cookies=True
    )
    return LinkedInClient(client)


# Singleton instance
_linkedin_client: Optional[LinkedInClient] = None
_linkedin_error: Optional[str] = None


def get_linkedin_client(
    email: Optional[str] = None,
    password: Optional[str] = None
) -> Tuple[Optional[LinkedInClient], Optional[str]]:
    """
    Get or create the LinkedIn client singleton.
    
    Authentication is attempted in this order:
    1. Username/password (if provided or in env)
    2. Browser cookies (Brave, Chrome, Firefox, Edge)
    3. Environment variable cookies (LINKEDIN_LI_AT, LINKEDIN_JSESSIONID)
    
    Args:
        email: LinkedIn email (optional, falls back to LINKEDIN_EMAIL env)
        password: LinkedIn password (optional, falls back to LINKEDIN_PASSWORD env)
    
    Returns:
        Tuple of (client, error_message). One will be None.
    """
    global _linkedin_client, _linkedin_error
    
    if _linkedin_client is not None:
        return _linkedin_client, None
    
    if _linkedin_error is not None:
        return None, _linkedin_error
    
    _ensure_imports()
    
    # Get credentials from parameters or environment
    email = email or os.getenv("LINKEDIN_EMAIL")
    password = password or os.getenv("LINKEDIN_PASSWORD")
    
    # Try username/password login first
    if email and password:
        try:
            logger.info("Attempting LinkedIn login with username/password...")
            _linkedin_client = _create_client_with_credentials(email, password)
            logger.info("LinkedIn login successful with username/password")
            return _linkedin_client, None
        except Exception as e:
            logger.warning(f"Username/password login failed: {e}")
            # Fall through to try cookies
    
    # Try browser cookies
    cookies = _load_cookies_from_browsers()
    if cookies:
        try:
            _linkedin_client = _create_client_with_cookies(cookies)
            # Test the connection
            _linkedin_client.get_my_profile()
            logger.info("LinkedIn login successful with browser cookies")
            return _linkedin_client, None
        except Exception as e:
            logger.warning(f"Browser cookie login failed: {e}")
    
    # Try environment variable cookies
    cookies = _load_cookies_from_env()
    if cookies:
        try:
            _linkedin_client = _create_client_with_cookies(cookies)
            # Test the connection
            _linkedin_client.get_my_profile()
            logger.info("LinkedIn login successful with environment cookies")
            return _linkedin_client, None
        except Exception as e:
            logger.warning(f"Environment cookie login failed: {e}")
    
    # All methods failed
    _linkedin_error = (
        "LinkedIn authentication failed.\n\n"
        "To set up LinkedIn, use ONE of these methods:\n\n"
        "Option 1 - Username/Password:\n"
        "  Add to .env file:\n"
        "    LINKEDIN_EMAIL=your-email@example.com\n"
        "    LINKEDIN_PASSWORD=your-password\n"
        "  Note: May fail with 2FA or CAPTCHA challenges\n\n"
        "Option 2 - Browser Cookies (recommended):\n"
        "  1. Log into LinkedIn in Brave/Chrome/Firefox/Edge\n"
        "  2. Keep the browser open (cookies must be accessible)\n"
        "  3. The server will automatically extract cookies\n\n"
        "Option 3 - Manual Cookies:\n"
        "  1. Log into LinkedIn in your browser\n"
        "  2. Open DevTools → Application → Cookies → linkedin.com\n"
        "  3. Copy 'li_at' and 'JSESSIONID' values\n"
        "  4. Add to .env file:\n"
        "    LINKEDIN_LI_AT=your-li-at-cookie-value\n"
        "    LINKEDIN_JSESSIONID=your-jsessionid-value"
    )
    return None, _linkedin_error


def reset_linkedin_client():
    """Reset the singleton client (useful for re-authentication)."""
    global _linkedin_client, _linkedin_error
    _linkedin_client = None
    _linkedin_error = None

