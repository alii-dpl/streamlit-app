"""
Jira API Adapter - Handles HTTP requests to Jira
"""
import base64
import requests
from typing import Any, Dict, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from jira_types import Auth


def configure_headers(auth: Auth) -> Dict[str, str]:
    """Configure request headers for authentication"""
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    
    if auth and auth.username and auth.password:
        # Basic Auth for Jira Cloud (email:api_token)
        auth_string = f"{auth.username}:{auth.password}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        headers['Authorization'] = f"Basic {encoded}"
        print(f"Using Basic Auth with username: {auth.username}")
    
    return headers


def get_json(url: str, auth: Auth) -> Dict[str, Any]:
    """
    Fetch JSON from Jira API
    
    Args:
        url: The API URL to fetch
        auth: Authentication credentials
        
    Returns:
        JSON response as dictionary
    """
    headers = configure_headers(auth)
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 401:
            raise Exception("Unauthorized (401) - Check your credentials")
        
        if response.status_code != 200:
            print(f"Response body: {response.text[:500]}")
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching json from {url}")
        raise Exception(f"Request failed: {str(e)}")

