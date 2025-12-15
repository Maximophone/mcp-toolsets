#!/usr/bin/env python3
"""
LinkedIn Authentication Test Script

Tests that LinkedIn authentication is working correctly.
Run this before using the LinkedIn toolset to verify your setup.

Usage:
    python test_linkedin_auth.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


def print_header(title: str):
    """Print a section header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_status(label: str, status: bool, details: str = ""):
    """Print a status line."""
    icon = "✅" if status else "❌"
    line = f"{icon} {label}"
    if details:
        line += f": {details}"
    print(line)


def check_env_vars():
    """Check what environment variables are set."""
    print_header("Environment Variables")
    
    vars_to_check = [
        ("LINKEDIN_EMAIL", "Username/password auth"),
        ("LINKEDIN_PASSWORD", "Username/password auth"),
        ("LINKEDIN_LI_AT", "Cookie auth (li_at)"),
        ("LINKEDIN_JSESSIONID", "Cookie auth (JSESSIONID)"),
    ]
    
    any_auth_method = False
    
    for var_name, description in vars_to_check:
        value = os.getenv(var_name)
        if value:
            # Mask the value for security
            masked = value[:4] + "..." + value[-4:] if len(value) > 10 else "***"
            print_status(var_name, True, f"Set ({masked})")
            any_auth_method = True
        else:
            print_status(var_name, False, "Not set")
    
    # Check if we have at least one complete auth method
    has_credentials = os.getenv("LINKEDIN_EMAIL") and os.getenv("LINKEDIN_PASSWORD")
    has_cookies = os.getenv("LINKEDIN_LI_AT") and os.getenv("LINKEDIN_JSESSIONID")
    
    print()
    if has_credentials:
        print("📋 Username/password authentication is configured")
    if has_cookies:
        print("🍪 Cookie authentication is configured")
        
        # Validate cookie formats
        li_at = os.getenv("LINKEDIN_LI_AT", "")
        jsession = os.getenv("LINKEDIN_JSESSIONID", "")
        
        print()
        print("Cookie format check:")
        
        # Check li_at format
        if li_at.startswith("AQ"):
            print(f"  ✅ li_at starts with 'AQ' (correct)")
        else:
            print(f"  ⚠️  li_at doesn't start with 'AQ' - might be invalid")
            print(f"     Got: {li_at[:20]}...")
        
        # Check JSESSIONID format
        # Should be like: "ajax:1234567890123456789" (with quotes)
        jsession_clean = jsession.strip().strip("'")
        if jsession_clean.startswith('"ajax:') and jsession_clean.endswith('"'):
            print(f"  ✅ JSESSIONID format looks correct")
        elif jsession_clean.startswith('ajax:'):
            print(f"  ⚠️  JSESSIONID missing quotes - will be auto-fixed")
            print(f"     Tip: In .env, use: LINKEDIN_JSESSIONID='\"ajax:...\"'")
        else:
            print(f"  ⚠️  JSESSIONID format looks unusual")
            print(f"     Expected: \"ajax:1234567890\" (with quotes)")
            print(f"     Got: {jsession_clean[:30]}...")
        
    if not has_credentials and not has_cookies:
        print("⚠️  No complete authentication method configured in .env")
        print("   Will try to extract cookies from browser...")
    
    return has_credentials or has_cookies


def check_browser_cookies():
    """Check if we can extract cookies from browsers."""
    print_header("Browser Cookie Check")
    
    try:
        import browser_cookie3
        print_status("browser_cookie3", True, "Installed")
    except ImportError:
        print_status("browser_cookie3", False, "Not installed (pip install browser-cookie3)")
        return False
    
    browsers = [
        ("Brave", browser_cookie3.brave),
        ("Chrome", browser_cookie3.chrome),
        ("Firefox", browser_cookie3.firefox),
        ("Edge", browser_cookie3.edge),
    ]
    
    found_cookies = False
    
    for name, browser_func in browsers:
        try:
            cj = browser_func(domain_name='linkedin.com')
            has_li_at = any(c.name == "li_at" for c in cj)
            has_jsession = any(c.name.lower() == "jsessionid" for c in cj)
            
            if has_li_at and has_jsession:
                print_status(name, True, "LinkedIn cookies found!")
                found_cookies = True
            elif has_li_at or has_jsession:
                print_status(name, False, f"Partial cookies (li_at={has_li_at}, JSESSIONID={has_jsession})")
            else:
                print_status(name, False, "No LinkedIn cookies")
        except Exception as e:
            error_msg = str(e)
            if len(error_msg) > 50:
                error_msg = error_msg[:50] + "..."
            print_status(name, False, f"Error: {error_msg}")
    
    return found_cookies


def test_linkedin_connection():
    """Test actual LinkedIn API connection."""
    print_header("LinkedIn API Connection Test")
    
    try:
        from integrations.linkedin_client import get_linkedin_client, reset_linkedin_client
        
        # Reset any cached client
        reset_linkedin_client()
        
        print("Attempting to connect to LinkedIn...")
        print("(This may take a few seconds)")
        print()
        
        client, error = get_linkedin_client()
        
        if error:
            print_status("Connection", False, "Failed")
            print()
            print("Error details:")
            print("-" * 40)
            # Print just the first part of the error (setup instructions are long)
            error_lines = error.split("\n")
            for line in error_lines[:5]:
                print(f"  {line}")
            if len(error_lines) > 5:
                print("  ...")
            return False
        
        print_status("Connection", True, "Connected!")
        
        # Try to get our own profile
        print()
        print("Fetching your profile...")
        
        try:
            profile = client.get_my_profile()
            
            first_name = profile.get("firstName", profile.get("miniProfile", {}).get("firstName", ""))
            last_name = profile.get("lastName", profile.get("miniProfile", {}).get("lastName", ""))
            name = f"{first_name} {last_name}".strip()
            
            headline = profile.get("headline", profile.get("miniProfile", {}).get("occupation", ""))
            
            print_status("Profile fetch", True, "Success!")
            print()
            print(f"  👤 Logged in as: {name}")
            if headline:
                print(f"  💼 {headline}")
            
            # Try to get public ID
            public_id = profile.get("public_id") or profile.get("miniProfile", {}).get("publicIdentifier", "")
            if public_id:
                print(f"  🔗 linkedin.com/in/{public_id}")
            
            return True
            
        except Exception as e:
            print_status("Profile fetch", False, str(e))
            return False
        
    except ImportError as e:
        print_status("Import", False, f"Missing dependency: {e}")
        print()
        print("Try: pip install linkedin-api")
        return False
    except Exception as e:
        print_status("Connection", False, str(e))
        return False


def main():
    """Run all authentication tests."""
    print()
    print("🔗 LinkedIn Authentication Test")
    print("=" * 60)
    
    # Check environment variables
    has_env_auth = check_env_vars()
    
    # Check browser cookies
    has_browser_cookies = check_browser_cookies()
    
    # Test actual connection
    connection_ok = test_linkedin_connection()
    
    # Summary
    print_header("Summary")
    
    if connection_ok:
        print("✅ LinkedIn authentication is working!")
        print()
        print("You can now use the LinkedIn toolset.")
        print("Enable it in .env: MCP_ENABLED_TOOLSETS=system,linkedin")
    else:
        print("❌ LinkedIn authentication failed")
        print()
        print("Troubleshooting steps:")
        print("1. Make sure you're logged into LinkedIn in your browser")
        print("2. Try closing and reopening your browser")
        print("3. Manually extract cookies (see README.md for instructions)")
        print("4. Add LINKEDIN_LI_AT and LINKEDIN_JSESSIONID to .env")
    
    print()
    return 0 if connection_ok else 1


if __name__ == "__main__":
    sys.exit(main())

