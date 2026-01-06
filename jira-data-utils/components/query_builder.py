"""
Query Builder - Builds Jira API URLs
"""
from urllib.parse import quote


def build_api_url(root_url: str) -> str:
    """Build the API base URL"""
    root_url = root_url.rstrip('/')
    return f"{root_url}/rest/api/3"


def build_jira_search_query_url_with_token(
    api_root_url: str,
    batch_size: int,
    jql: str,
    next_page_token: str = None
) -> str:
    """
    Build Jira search query URL with pagination token
    
    Args:
        api_root_url: Jira instance URL
        batch_size: Number of results per page
        jql: JQL query string
        next_page_token: Optional pagination token
        
    Returns:
        Complete API URL
    """
    root_url = api_root_url.rstrip('/')
    encoded_jql = quote(jql, safe='')
    
    query = (
        f"{root_url}/rest/api/3/search/jql"
        f"?jql={encoded_jql}"
        f"&maxResults={batch_size}"
        f"&fields=*all"
        f"&expand=changelog"
    )
    
    if next_page_token:
        query += f"&nextPageToken={quote(next_page_token, safe='')}"
    
    return query

