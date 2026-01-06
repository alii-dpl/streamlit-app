"""
Jira Extractor - Main extraction logic
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from typing import Callable, Dict, List, Optional, Any
from jira_types import JiraExtractorConfig, DurationIntervals, JiraApiIssue
from components.jira_adapter import get_json
from components.query_builder import build_jira_search_query_url_with_token
from components.fields_parser import get_attributes
from components.staging_parser import populate_stages
from components.jira_work_item import JiraWorkItem


class JiraExtractor:
    """
    Main Jira data extractor class
    
    Extracts issues from Jira and calculates stage durations
    """
    
    def __init__(self, config: JiraExtractorConfig):
        self.config = config
        self.config.batch_size = 25
    
    def validate(self) -> bool:
        """
        Validate the configuration and connection
        
        Returns:
            True if validation passes
            
        Raises:
            Exception if validation fails
        """
        api_root_url = self.config.connection.url
        if not api_root_url:
            raise Exception('URL for extraction not set.')
        
        jql = self._get_jql()
        query_url = build_jira_search_query_url_with_token(api_root_url, 1, jql)
        
        print(f"Validating with URL: {query_url}")
        test_response = get_json(query_url, self.config.connection.auth)
        print(f"API Response keys: {list(test_response.keys())}")
        
        # Check for error response
        if test_response.get('error'):
            raise Exception(f"Jira API Error: {test_response['error']}")
        
        error_messages = test_response.get('errorMessages', [])
        if error_messages:
            raise Exception('\n'.join(error_messages))
        
        issues = test_response.get('issues', [])
        if not issues:
            raise Exception(
                f"No JIRA Issues found with the generated JQL:\n{jql}\n"
                "Please modify your configuration."
            )
        
        print(f"Validation passed. Found {len(issues)} issues.")
        return True
    
    def extract_all(
        self,
        status_hook: Callable[[int], None] = None,
        debug: bool = False
    ) -> List[JiraWorkItem]:
        """
        Extract all issues matching the JQL query
        
        Args:
            status_hook: Optional callback for progress updates (0-100)
            debug: Enable debug output
            
        Returns:
            List of JiraWorkItem objects
        """
        self.validate()
        
        if status_hook is None:
            status_hook = lambda n: None
        
        api_root_url = self.config.connection.url
        auth = self.config.connection.auth
        batch_size = self.config.batch_size or 25
        jql = self._get_jql()
        
        if debug:
            print(f"Using the following JQL for extracting:\n{jql}\n")
        
        work_items: List[JiraWorkItem] = []
        next_page_token: Optional[str] = None
        page_count = 0
        is_last = False
        
        status_hook(0)
        
        # Use cursor-based pagination with nextPageToken
        while not is_last:
            query_url = build_jira_search_query_url_with_token(
                api_root_url, batch_size, jql, next_page_token
            )
            response = get_json(query_url, auth)
            
            error_messages = response.get('errorMessages', [])
            if error_messages:
                print(f"API Error: {error_messages}")
                break
            
            issues = response.get('issues', [])
            if issues:
                if page_count == 0 and debug:
                    print(f"First sample: {issues[0].get('fields', {})}")
                
                print(f" Parsing page {page_count + 1}, got {len(issues)} issues")
                
                for issue in issues:
                    work_item = self._convert_issue_to_work_item(issue)
                    work_items.append(work_item)
                
                # Update progress
                status_hook(min((page_count + 1) * 10, 90))
            
            # Check if there are more pages
            next_page_token = response.get('nextPageToken')
            is_last = response.get('isLast', True) or not next_page_token
            page_count += 1
            
            # Safety limit
            if page_count > 1000:
                print("Safety limit reached: 1000 pages")
                break
        
        status_hook(100)
        print(f"Total issues extracted: {len(work_items)}")
        
        return work_items
    
    def to_csv(self, work_items: List[JiraWorkItem]) -> str:
        """
        Convert work items to CSV string
        
        Args:
            work_items: List of work items to convert
            
        Returns:
            CSV string
        """
        print(" Extracting to csv ..")
        SEP = ';'
        
        attributes = self.config.attributes or {}
        stage_names = self._get_stage_names(work_items)
        stage_header_names = self._get_header_stage_names(stage_names)
        stage_start_names = self._get_header_stage_start_date_names(stage_names)
        stage_recurrence_names = self._get_header_stage_recurrence_names(stage_names)
        
        # Build header
        header_arr = ['ID', 'Link', 'Name', 'Type']
        header_arr.extend(stage_header_names)
        header_arr.extend(stage_start_names)
        header_arr.extend(stage_recurrence_names)
        header_arr.extend(attributes.keys())
        header_arr = [JiraWorkItem.clean_string(h) for h in header_arr]
        header = SEP.join(header_arr)
        
        # Build body
        body_lines = []
        for item in work_items:
            row = item.to_csv(self.config, stage_names)
            body_lines.append(SEP.join(row))
        
        body = '\n'.join(body_lines)
        csv = f"{header}\n{body}\n"
        
        return csv
    
    def _get_jql(self) -> str:
        """Get the JQL query string"""
        return self.config.custom_jql
    
    def _get_stage_names(self, work_items: List[JiraWorkItem]) -> List[str]:
        """Get unique stage names from all work items"""
        unique_names = set()
        
        for item in work_items:
            unique_names.update(item.stages.keys())
        
        return list(unique_names)
    
    def _get_header_stage_names(self, stage_names: List[str]) -> List[str]:
        """Generate header names for stage duration columns"""
        return [f"Stage {name} days" for name in stage_names]
    
    def _get_header_stage_start_date_names(self, stage_names: List[str]) -> List[str]:
        """Generate header names for stage start date columns"""
        return [f"Stage {name} start" for name in stage_names]
    
    def _get_header_stage_recurrence_names(self, stage_names: List[str]) -> List[str]:
        """Generate header names for stage recurrence columns"""
        return [f"Stage {name} recurrence" for name in stage_names]
    
    def _convert_issue_to_work_item(self, issue: JiraApiIssue) -> JiraWorkItem:
        """Convert a Jira API issue to a JiraWorkItem"""
        attributes = self.config.attributes or {}
        
        key = issue.get('key', '')
        fields = issue.get('fields', {})
        name = fields.get('summary', '')
        staging_dates = populate_stages(issue)
        
        issue_type = ''
        if fields.get('issuetype'):
            issue_type = fields['issuetype'].get('name', '')
        
        # Extract requested attributes
        attributes_key_val = {}
        if attributes:
            requested_attr_names = list(attributes.values())
            attributes_key_val = get_attributes(fields, requested_attr_names)
        
        return JiraWorkItem(
            id=key,
            stages=staging_dates,
            name=name,
            type=issue_type,
            attributes=attributes_key_val
        )
