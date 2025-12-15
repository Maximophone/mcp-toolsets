"""
LinkedIn Toolset

Tools for interacting with LinkedIn - profile lookups, people search,
messaging, and batch data retrieval.

IMPORTANT: This uses an unofficial API. Rate limits are enforced to
avoid account restrictions. Daily limits and delays between operations
are configured conservatively.

Rate Limits (default):
- Profile reads: 10-30s delay, 500/day
- Searches: 30-60s delay, 100/day
- Messages: 60-180s delay, 100/day
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .base import tool, RegisteredTool
from integrations.linkedin_client import (
    get_linkedin_client,
    LinkedInClient,
    LinkedInMessageError,
)
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


# ============ Rate Limiters ============
# Conservative limits for the unofficial API

_profile_limiter = RateLimiter(
    name="linkedin_profiles",
    min_delay_seconds=10.0,
    max_delay_seconds=30.0,
    max_per_day=500,
    night_mode=False,
)

_search_limiter = RateLimiter(
    name="linkedin_search",
    min_delay_seconds=30.0,
    max_delay_seconds=60.0,
    max_per_day=100,
    night_mode=False,
)

_message_limiter = RateLimiter(
    name="linkedin_messages",
    min_delay_seconds=60.0,
    max_delay_seconds=180.0,
    max_per_day=100,
    night_mode=False,
)


def _get_client() -> LinkedInClient:
    """Get LinkedIn client or raise error."""
    client, error = get_linkedin_client()
    if error:
        raise RuntimeError(error)
    return client


def _format_profile(profile: Dict[str, Any], verbose: bool = False) -> str:
    """Format a profile for display."""
    lines = []
    
    # Handle nested miniProfile structure
    mini = profile.get("miniProfile", {})
    
    # Name and headline - try multiple sources
    first_name = profile.get("firstName") or mini.get("firstName", "")
    last_name = profile.get("lastName") or mini.get("lastName", "")
    name = f"{first_name} {last_name}".strip() or "(No name)"
    headline = profile.get("headline") or profile.get("occupation") or mini.get("occupation", "")
    
    lines.append(f"**{name}**")
    if headline:
        lines.append(f"_{headline}_")
    
    # Identifiers
    public_id = profile.get("public_id") or profile.get("publicIdentifier", "")
    urn_id = profile.get("urn_id") or profile.get("entityUrn", "")
    if urn_id and ":" in urn_id:
        urn_id = urn_id.split(":")[-1]
    
    if public_id:
        lines.append(f"Public ID: {public_id}")
    if urn_id:
        lines.append(f"URN ID: {urn_id}")
    
    # Location
    location = profile.get("locationName") or profile.get("geoLocationName", "")
    if location:
        lines.append(f"Location: {location}")
    
    # Industry
    industry = profile.get("industryName", "")
    if industry:
        lines.append(f"Industry: {industry}")
    
    # Current position
    experience = profile.get("experience", [])
    if experience:
        current = experience[0]  # Most recent
        company = current.get("companyName", "")
        title = current.get("title", "")
        if company or title:
            lines.append(f"Current: {title} at {company}".strip())
    
    # Summary (if verbose)
    if verbose:
        summary = profile.get("summary", "")
        if summary:
            lines.append("")
            lines.append("**Summary:**")
            # Truncate long summaries
            if len(summary) > 500:
                summary = summary[:500] + "..."
            lines.append(summary)
        
        # Education
        education = profile.get("education", [])
        if education:
            lines.append("")
            lines.append("**Education:**")
            for edu in education[:3]:  # Top 3
                school = edu.get("schoolName", "")
                degree = edu.get("degreeName", "")
                field = edu.get("fieldOfStudy", "")
                if school:
                    edu_line = f"- {school}"
                    if degree or field:
                        edu_line += f": {degree} {field}".strip()
                    lines.append(edu_line)
    
    return "\n".join(lines)


def _format_search_result(result: Dict[str, Any]) -> str:
    """Format a search result for display."""
    lines = []
    
    # Handle nested miniProfile structure (from connections)
    mini = result.get("miniProfile", {})
    
    # Name - try multiple sources
    first_name = result.get("firstName") or mini.get("firstName", "")
    last_name = result.get("lastName") or mini.get("lastName", "")
    name = f"{first_name} {last_name}".strip() or "(No name)"
    
    # URN - try multiple sources
    urn_id = result.get("urn_id") or result.get("entityUrn") or mini.get("entityUrn", "")
    if urn_id and ":" in urn_id:
        urn_id = urn_id.split(":")[-1]
    
    public_id = result.get("public_id") or result.get("publicIdentifier") or mini.get("publicIdentifier", "")
    
    lines.append(f"• **{name}**")
    
    # Headline/title - try multiple sources
    headline = (result.get("headline") or result.get("jobtitle") or 
                result.get("occupation") or mini.get("occupation", ""))
    if headline:
        lines.append(f"  {headline}")
    
    # Location
    location = result.get("location") or result.get("locationName", "")
    if location:
        lines.append(f"  📍 {location}")
    
    # IDs
    if public_id:
        lines.append(f"  Public ID: {public_id}")
    if urn_id:
        lines.append(f"  URN ID: {urn_id}")
    
    return "\n".join(lines)


def _format_conversation_preview(conv: Dict[str, Any]) -> str:
    """Format a conversation for the list view."""
    lines = []
    
    # Get participants
    participants = conv.get("participants", [])
    names = []
    for p in participants:
        member = p.get("com.linkedin.voyager.messaging.MessagingMember", {})
        mini = member.get("miniProfile", {})
        first = mini.get("firstName", "")
        last = mini.get("lastName", "")
        name = f"{first} {last}".strip()
        if name:
            names.append(name)
    
    participant_str = ", ".join(names[:3])
    if len(names) > 3:
        participant_str += f" (+{len(names) - 3} more)"
    
    # Get conversation URN
    conv_urn = conv.get("entityUrn", "")
    conv_id = ""
    if "fs_conversation:" in conv_urn:
        conv_id = conv_urn.split("fs_conversation:")[-1]
    
    # Last activity
    last_activity = conv.get("lastActivityAt", 0)
    if last_activity:
        try:
            dt = datetime.fromtimestamp(last_activity / 1000)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = ""
    else:
        time_str = ""
    
    # Unread count
    unread = conv.get("unreadCount", 0)
    unread_str = f" 🔴 {unread} unread" if unread > 0 else ""
    
    lines.append(f"• **{participant_str}**{unread_str}")
    if time_str:
        lines.append(f"  Last activity: {time_str}")
    if conv_id:
        lines.append(f"  Conversation ID: {conv_id}")
    
    return "\n".join(lines)


def _format_message(msg: Dict[str, Any]) -> str:
    """Format a single message."""
    lines = []
    
    # Sender
    sender = msg.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {})
    mini = sender.get("miniProfile", {})
    first = mini.get("firstName", "")
    last = mini.get("lastName", "")
    name = f"{first} {last}".strip() or "(Unknown)"
    
    # Timestamp
    timestamp = msg.get("createdAt", 0)
    if timestamp:
        try:
            dt = datetime.fromtimestamp(timestamp / 1000)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = ""
    else:
        time_str = ""
    
    # Message body
    event_content = msg.get("eventContent", {})
    msg_event = event_content.get("com.linkedin.voyager.messaging.event.MessageEvent", {})
    
    body = ""
    attr_body = msg_event.get("attributedBody", {})
    if attr_body:
        body = attr_body.get("text", "")
    if not body:
        body = msg_event.get("body", "")
    
    # Format
    header = f"**{name}**"
    if time_str:
        header += f" ({time_str})"
    
    lines.append(header)
    if body:
        lines.append(body)
    else:
        lines.append("_(No text content)_")
    
    return "\n".join(lines)


# ============ Profile Tools (Safe/Read-only) ============

@tool(
    description="Get a LinkedIn profile by public ID or URN ID. Returns profile details including name, headline, location, current position, and more.",
    public_id="The public profile ID from the LinkedIn URL (e.g., 'john-doe-123456' from linkedin.com/in/john-doe-123456)",
    urn_id="The URN ID (e.g., 'ACoAABxxxx'). Use this if you have it from a previous search.",
    verbose="Whether to include full details like summary and education (default: false)",
    safe=True
)
def get_linkedin_profile(
    public_id: str = "",
    urn_id: str = "",
    verbose: bool = False
) -> str:
    """Get a LinkedIn profile."""
    if not public_id and not urn_id:
        return "Error: Must provide either public_id or urn_id"
    
    # Rate limiting
    if not _profile_limiter.wait():
        remaining = _profile_limiter.get_remaining_today()
        return f"Daily limit reached for profile lookups. Remaining today: {remaining}"
    
    try:
        client = _get_client()
        profile = client.get_profile(
            public_id=public_id if public_id else None,
            urn_id=urn_id if urn_id else None
        )
        
        _profile_limiter.record_success()
        return _format_profile(profile, verbose=verbose)
        
    except Exception as e:
        _profile_limiter.record_failure()
        return f"Error fetching profile: {str(e)}"


@tool(
    description="Get the authenticated user's own LinkedIn profile.",
    safe=True
)
def get_my_linkedin_profile() -> str:
    """Get the authenticated user's profile."""
    try:
        client = _get_client()
        profile = client.get_my_profile()
        return _format_profile(profile, verbose=True)
    except Exception as e:
        return f"Error fetching your profile: {str(e)}"


@tool(
    description="Get contact information for a LinkedIn profile (email, phone, etc. if available). Note: This only shows info the user has chosen to share.",
    public_id="The public profile ID",
    urn_id="The URN ID",
    safe=True
)
def get_linkedin_contact_info(
    public_id: str = "",
    urn_id: str = ""
) -> str:
    """Get contact info for a profile."""
    if not public_id and not urn_id:
        return "Error: Must provide either public_id or urn_id"
    
    if not _profile_limiter.wait():
        return "Daily limit reached for profile lookups."
    
    try:
        client = _get_client()
        info = client.get_profile_contact_info(
            public_id=public_id if public_id else None,
            urn_id=urn_id if urn_id else None
        )
        
        _profile_limiter.record_success()
        
        if not info:
            return "No contact information available."
        
        lines = ["**Contact Information:**"]
        
        # Email
        email_addr = info.get("email_address")
        if email_addr:
            lines.append(f"📧 Email: {email_addr}")
        
        # Phone
        phones = info.get("phone_numbers", [])
        for phone in phones:
            number = phone.get("number", "")
            phone_type = phone.get("type", "")
            if number:
                lines.append(f"📱 Phone ({phone_type}): {number}")
        
        # Websites
        websites = info.get("websites", [])
        for site in websites:
            url = site.get("url", "")
            site_type = site.get("type", {}).get("category", "")
            if url:
                lines.append(f"🔗 Website ({site_type}): {url}")
        
        # Twitter
        twitter = info.get("twitter_handles", [])
        for handle in twitter:
            lines.append(f"🐦 Twitter: @{handle}")
        
        if len(lines) == 1:
            return "No contact information available."
        
        return "\n".join(lines)
        
    except Exception as e:
        _profile_limiter.record_failure()
        return f"Error fetching contact info: {str(e)}"


# ============ Search Tools (Safe/Read-only) ============

@tool(
    description="Search for people on LinkedIn. Returns matching profiles with their basic info and IDs for further lookup.",
    keywords="Search keywords (e.g., 'software engineer', 'marketing manager')",
    connection_level="Filter by connection level: '1st' (direct connections), '2nd' (friends of friends), '3rd' (everyone else). Leave empty for all.",
    limit="Maximum number of results (default: 10, max: 50)",
    safe=True
)
def search_linkedin_people(
    keywords: str = "",
    connection_level: str = "",
    limit: int = 10
) -> str:
    """Search for people on LinkedIn."""
    if not keywords:
        return "Error: Please provide search keywords"
    
    if not _search_limiter.wait():
        remaining = _search_limiter.get_remaining_today()
        return f"Daily limit reached for searches. Remaining today: {remaining}"
    
    # Map connection level to network depth
    network_depths = None
    if connection_level:
        depth_map = {
            "1st": ["F"],
            "1": ["F"],
            "first": ["F"],
            "2nd": ["S"],
            "2": ["S"],
            "second": ["S"],
            "3rd": ["O"],
            "3": ["O"],
            "third": ["O"],
        }
        network_depths = depth_map.get(connection_level.lower())
    
    # Cap limit
    limit = min(limit, 50)
    
    try:
        client = _get_client()
        results = client.search_people(
            keywords=keywords,
            network_depths=network_depths,
            limit=limit
        )
        
        _search_limiter.record_success()
        
        if not results:
            return f"No results found for '{keywords}'"
        
        output = [f"**Search Results for '{keywords}'**"]
        output.append(f"Found {len(results)} result(s):\n")
        
        for result in results:
            output.append(_format_search_result(result))
            output.append("")  # Spacing
        
        # Add note about rate limits
        remaining = _search_limiter.get_remaining_today()
        output.append(f"---\n_Searches remaining today: {remaining}_")
        
        return "\n".join(output)
        
    except Exception as e:
        _search_limiter.record_failure()
        return f"Error searching: {str(e)}"


@tool(
    description="Get your LinkedIn connections. Returns a list of your 1st-degree connections with their basic info.",
    limit="Maximum number of connections to return (default: 50, max: 200)",
    safe=True
)
def get_my_linkedin_connections(limit: int = 50) -> str:
    """Get the user's connections."""
    if not _profile_limiter.wait():
        return "Daily limit reached."
    
    limit = min(limit, 200)
    
    try:
        client = _get_client()
        connections = client.get_connections(limit=limit)
        
        _profile_limiter.record_success()
        
        if not connections:
            return "No connections found."
        
        output = [f"**Your LinkedIn Connections**"]
        output.append(f"Showing {len(connections)} connection(s):\n")
        
        for conn in connections:
            output.append(_format_search_result(conn))
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        _profile_limiter.record_failure()
        return f"Error fetching connections: {str(e)}"


# ============ Messaging Tools (Read operations - Safe) ============

@tool(
    description="List your LinkedIn conversations (message threads). Shows recent conversations with participants and last activity.",
    safe=True
)
def list_linkedin_conversations() -> str:
    """List all conversations."""
    try:
        client = _get_client()
        conversations = client.get_conversations()
        
        if not conversations:
            return "No conversations found."
        
        output = ["**Your LinkedIn Conversations**"]
        output.append(f"Found {len(conversations)} conversation(s):\n")
        
        for conv in conversations[:20]:  # Limit display to 20
            output.append(_format_conversation_preview(conv))
            output.append("")
        
        if len(conversations) > 20:
            output.append(f"_(Showing 20 of {len(conversations)} conversations)_")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error fetching conversations: {str(e)}"


@tool(
    description="Get messages from a specific LinkedIn conversation.",
    conversation_id="The conversation ID (from list_linkedin_conversations)",
    safe=True
)
def get_linkedin_conversation(conversation_id: str) -> str:
    """Get messages from a conversation."""
    if not conversation_id:
        return "Error: Please provide a conversation_id"
    
    try:
        client = _get_client()
        conversation = client.get_conversation(conversation_id)
        
        elements = conversation.get("elements", [])
        
        if not elements:
            return "No messages in this conversation."
        
        # Sort by timestamp (oldest first for reading)
        elements.sort(key=lambda x: x.get("createdAt", 0))
        
        output = ["**Conversation Messages**"]
        output.append(f"Total: {len(elements)} message(s)\n")
        
        for msg in elements:
            output.append(_format_message(msg))
            output.append("---")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error fetching conversation: {str(e)}"


# ============ Messaging Tools (Write operations - Unsafe) ============

@tool(
    description="Send a direct message to a LinkedIn user. IMPORTANT: Use sparingly to avoid account restrictions. Rate limited to ~100 messages per day with 60-180 second delays.",
    recipient_urn="The URN ID of the recipient (e.g., 'ACoAABxxxx' - get this from profile lookup or search)",
    message="The message text to send",
    safe=False
)
def send_linkedin_message(recipient_urn: str, message: str) -> str:
    """Send a message to a LinkedIn user."""
    if not recipient_urn:
        return "Error: Please provide recipient_urn"
    if not message:
        return "Error: Please provide a message"
    if len(message) > 8000:
        return "Error: Message too long (max 8000 characters)"
    
    # Check rate limit
    if not _message_limiter.wait():
        remaining = _message_limiter.get_remaining_today()
        return f"Daily message limit reached. Remaining today: {remaining}"
    
    try:
        client = _get_client()
        
        # Send the message
        client.send_message(
            message_body=message,
            recipients=[recipient_urn]
        )
        
        _message_limiter.record_success()
        
        remaining = _message_limiter.get_remaining_today()
        return (
            f"✅ Message sent successfully!\n"
            f"Recipient URN: {recipient_urn}\n"
            f"Message length: {len(message)} characters\n"
            f"---\n"
            f"_Messages remaining today: {remaining}_"
        )
        
    except LinkedInMessageError as e:
        _message_limiter.record_failure()
        return f"❌ Failed to send message: {str(e)}"
    except Exception as e:
        _message_limiter.record_failure()
        return f"❌ Error sending message: {str(e)}"


@tool(
    description="Reply to an existing LinkedIn conversation.",
    conversation_id="The conversation ID (from list_linkedin_conversations)",
    message="The reply message text",
    safe=False
)
def reply_to_linkedin_conversation(conversation_id: str, message: str) -> str:
    """Reply to an existing conversation."""
    if not conversation_id:
        return "Error: Please provide conversation_id"
    if not message:
        return "Error: Please provide a message"
    if len(message) > 8000:
        return "Error: Message too long (max 8000 characters)"
    
    if not _message_limiter.wait():
        remaining = _message_limiter.get_remaining_today()
        return f"Daily message limit reached. Remaining today: {remaining}"
    
    try:
        client = _get_client()
        
        client.send_message(
            message_body=message,
            conversation_urn_id=conversation_id
        )
        
        _message_limiter.record_success()
        
        remaining = _message_limiter.get_remaining_today()
        return (
            f"✅ Reply sent successfully!\n"
            f"Conversation: {conversation_id}\n"
            f"---\n"
            f"_Messages remaining today: {remaining}_"
        )
        
    except LinkedInMessageError as e:
        _message_limiter.record_failure()
        return f"❌ Failed to send reply: {str(e)}"
    except Exception as e:
        _message_limiter.record_failure()
        return f"❌ Error sending reply: {str(e)}"


# ============ Batch Tools (Unsafe - but read operations) ============

@tool(
    description="Get multiple LinkedIn profiles in batch. More efficient than individual lookups. Rate limited to prevent account issues.",
    profile_ids_json="JSON array of profile identifiers. Each item should be an object with 'public_id' and/or 'urn_id'. Example: '[{\"public_id\": \"john-doe\"}, {\"urn_id\": \"ACoAABxxxx\"}]'",
    safe=False  # Marked unsafe due to batch nature, even though it's read-only
)
def batch_get_linkedin_profiles(profile_ids_json: str) -> str:
    """Batch fetch multiple profiles."""
    try:
        profiles_to_fetch = json.loads(profile_ids_json)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON - {e}"
    
    if not isinstance(profiles_to_fetch, list):
        return "Error: profile_ids_json must be a JSON array"
    
    if len(profiles_to_fetch) > 20:
        return "Error: Maximum 20 profiles per batch (to respect rate limits)"
    
    if len(profiles_to_fetch) == 0:
        return "Error: No profiles specified"
    
    client = _get_client()
    
    results = []
    errors = []
    
    for i, profile_spec in enumerate(profiles_to_fetch):
        public_id = profile_spec.get("public_id", "")
        urn_id = profile_spec.get("urn_id", "")
        
        if not public_id and not urn_id:
            errors.append(f"Item {i+1}: Missing public_id or urn_id")
            continue
        
        # Rate limiting
        if not _profile_limiter.wait():
            errors.append(f"Item {i+1}: Daily limit reached, stopping batch")
            break
        
        try:
            profile = client.get_profile(
                public_id=public_id if public_id else None,
                urn_id=urn_id if urn_id else None
            )
            _profile_limiter.record_success()
            results.append({
                "index": i + 1,
                "public_id": public_id,
                "urn_id": urn_id,
                "profile": _format_profile(profile, verbose=False)
            })
        except Exception as e:
            _profile_limiter.record_failure()
            errors.append(f"Item {i+1} ({public_id or urn_id}): {str(e)}")
    
    # Format output
    output = [f"**Batch Profile Results**"]
    output.append(f"Requested: {len(profiles_to_fetch)}, Retrieved: {len(results)}, Errors: {len(errors)}\n")
    
    for result in results:
        output.append(f"--- Profile {result['index']} ---")
        output.append(result["profile"])
        output.append("")
    
    if errors:
        output.append("**Errors:**")
        for error in errors:
            output.append(f"• {error}")
    
    remaining = _profile_limiter.get_remaining_today()
    output.append(f"\n_Profile lookups remaining today: {remaining}_")
    
    return "\n".join(output)


# ============ Status Tool ============

@tool(
    description="Get current LinkedIn rate limit status. Shows how many operations are remaining today for each type.",
    safe=True
)
def get_linkedin_rate_limit_status() -> str:
    """Get rate limit status."""
    profile_status = _profile_limiter.get_status()
    search_status = _search_limiter.get_status()
    message_status = _message_limiter.get_status()
    
    lines = ["**LinkedIn Rate Limit Status**\n"]
    
    # Profile limits
    lines.append("📋 **Profile Lookups**")
    lines.append(f"   Today: {profile_status['operations_today']}/{profile_status['max_per_day']}")
    lines.append(f"   Remaining: {profile_status['remaining_today']}")
    lines.append("")
    
    # Search limits
    lines.append("🔍 **Searches**")
    lines.append(f"   Today: {search_status['operations_today']}/{search_status['max_per_day']}")
    lines.append(f"   Remaining: {search_status['remaining_today']}")
    lines.append("")
    
    # Message limits
    lines.append("💬 **Messages**")
    lines.append(f"   Today: {message_status['operations_today']}/{message_status['max_per_day']}")
    lines.append(f"   Remaining: {message_status['remaining_today']}")
    lines.append("")
    
    # Note about limits
    lines.append("---")
    lines.append("_Limits reset at midnight. Conservative limits are enforced to protect your account._")
    
    return "\n".join(lines)


# ============ Export Tools List ============

TOOLS: List[RegisteredTool] = [
    # Profile tools (safe)
    get_linkedin_profile,
    get_my_linkedin_profile,
    get_linkedin_contact_info,
    
    # Search tools (safe)
    search_linkedin_people,
    get_my_linkedin_connections,
    
    # Messaging - read (safe)
    list_linkedin_conversations,
    get_linkedin_conversation,
    
    # Messaging - write (unsafe)
    send_linkedin_message,
    reply_to_linkedin_conversation,
    
    # Batch tools (unsafe due to volume)
    batch_get_linkedin_profiles,
    
    # Status (safe)
    get_linkedin_rate_limit_status,
]

