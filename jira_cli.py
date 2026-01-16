#!/usr/bin/env python3
"""
Jira Data Extraction CLI

Extract Jira issues using a JQL query and output CSV.

Usage:
    python jira_cli.py "Sprint = 'iApts 2025-26'" [--output output.csv]
    python jira_cli.py "project = DEV AND status = Done" --output results.csv
    
    # Using environment variables for credentials:
    export JIRA_DOMAIN="https://your-domain.atlassian.net/"
    export JIRA_USERNAME="your-email@company.com"
    export JIRA_PASSWORD="your-api-token"
    
    # Or use a config file (see --config option)
    python jira_cli.py "Sprint = 'iApts 2025-26'" --config .streamlit/secrets.toml

Environment Variables:
    JIRA_DOMAIN: Jira instance URL (required)
    JIRA_USERNAME: Jira username/email (required)
    JIRA_PASSWORD: Jira API token (required)
"""
import sys
import os
import argparse
from pathlib import Path
from typing import Dict, Optional

# Add jira-data-utils to path
sys.path.insert(0, str(Path(__file__).parent / 'jira-data-utils'))

from extractor import JiraExtractor
from jira_types import JiraExtractorConfig, Auth, ConnectionConfig


def load_credentials_from_env() -> Dict[str, str]:
    """Load Jira credentials from environment variables"""
    domain = os.getenv('JIRA_DOMAIN')
    username = os.getenv('JIRA_USERNAME')
    password = os.getenv('JIRA_PASSWORD')
    
    if not all([domain, username, password]):
        missing = []
        if not domain:
            missing.append('JIRA_DOMAIN')
        if not username:
            missing.append('JIRA_USERNAME')
        if not password:
            missing.append('JIRA_PASSWORD')
        
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please set them or use --config option."
        )
    
    return {
        'domain': domain,
        'username': username,
        'password': password,
    }


def load_credentials_from_toml(config_path: Path) -> Dict[str, str]:
    """Load Jira credentials from TOML config file (Streamlit secrets format)"""
    # Try to import TOML parser
    toml_parser = None
    
    # Python 3.11+ has tomllib built-in
    try:
        import tomllib
        toml_parser = tomllib
    except ImportError:
        pass
    
    # Try tomli (backport for older Python)
    if not toml_parser:
        try:
            import tomli
            toml_parser = tomli
        except ImportError:
            pass
    
    # Try toml package
    if not toml_parser:
        try:
            import toml
            toml_parser = toml
        except ImportError:
            raise ImportError(
                "TOML parsing requires 'tomli' or 'toml' package.\n"
                "Install with: pip install tomli\n"
                "Or use environment variables instead (JIRA_DOMAIN, JIRA_USERNAME, JIRA_PASSWORD)"
            )
    
    # Load TOML file
    # Check if parser is tomllib or tomli (binary mode)
    parser_name = toml_parser.__name__ if hasattr(toml_parser, '__name__') else ''
    if parser_name in ('tomllib', 'tomli'):
        with open(config_path, 'rb') as f:
            config = toml_parser.load(f)
    else:
        # toml package uses text mode
        with open(config_path, 'r') as f:
            config = toml_parser.load(f)
    
    jira_config = config.get('jira', {})
    
    if not jira_config:
        raise ValueError(f"No [jira] section found in {config_path}")
    
    domain = jira_config.get('domain')
    username = jira_config.get('username')
    password = jira_config.get('password')
    
    if not all([domain, username, password]):
        missing = []
        if not domain:
            missing.append('domain')
        if not username:
            missing.append('username')
        if not password:
            missing.append('password')
        raise ValueError(f"Missing required fields in config: {', '.join(missing)}")
    
    return {
        'domain': domain,
        'username': username,
        'password': password,
    }


def get_default_attributes() -> Dict[str, str]:
    """Get default attributes to extract (same as Streamlit app)"""
    return {
        'Stage': 'status.name',
        'StatusCategory': 'status.statusCategory.name',
        'Level': 'priority.name',
        'Labels': 'labels',
        'Components': 'components.name',
        'Version': 'fixVersions.last.name',
        'VersionRelease': 'fixVersions.last.releaseDate',
        'ParentId': 'parent.key',
        'ParentName': 'parent.fields.summary',
        'ParentType': 'parent.fields.issuetype.name',
        'AssigneeName': 'assignee.displayName',
        'LinksToOutwardKey': 'issuelinks.first.outwardIssue.key',
        'LinksToInwardKey': 'issuelinks.first.inwardIssue.key',
        'Timeoriginalestimate': 'timeoriginalestimate',
        'Timeestimate': 'timeestimate',
        'Timespent': 'timespent',
        'AggreagateTimeoriginalestimate': 'aggregatetimeoriginalestimate',
        'AggreagateTimeestimate': 'aggregatetimeestimate',
        'AggreagateTimespent': 'aggregatetimespent',
        'Workratio': 'workratio',
        'StoryPoints': 'customfield_10024',
        'QAStoryPoints': 'customfield_10158',
    }


def main():
    parser = argparse.ArgumentParser(
        description='Extract Jira issues using JQL query and output CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'query',
        type=str,
        help='JQL query string (e.g., "Sprint = \'iApts 2025-26\'")'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output CSV file path (default: stdout)'
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        default=None,
        help='Path to TOML config file with credentials (e.g., .streamlit/secrets.toml)'
    )
    
    parser.add_argument(
        '--domain',
        type=str,
        default=None,
        help='Jira domain URL (overrides env/config)'
    )
    
    parser.add_argument(
        '--username',
        type=str,
        default=None,
        help='Jira username (overrides env/config)'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        default=None,
        help='Jira API token (overrides env/config)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    
    args = parser.parse_args()
    
    # Load credentials (priority: command line > config file > environment)
    credentials = {}
    
    if args.domain and args.username and args.password:
        # Use command line arguments
        credentials = {
            'domain': args.domain,
            'username': args.username,
            'password': args.password,
        }
    elif args.config:
        # Load from config file
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        credentials = load_credentials_from_toml(config_path)
    else:
        # Load from environment variables
        try:
            credentials = load_credentials_from_env()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("\nAlternatively, use --config to specify a config file.", file=sys.stderr)
            sys.exit(1)
    
    # Override with command line args if provided individually
    if args.domain:
        credentials['domain'] = args.domain
    if args.username:
        credentials['username'] = args.username
    if args.password:
        credentials['password'] = args.password
    
    # Validate credentials
    if not all([credentials.get('domain'), credentials.get('username'), credentials.get('password')]):
        print("Error: Missing required credentials (domain, username, password)", file=sys.stderr)
        sys.exit(1)
    
    # Ensure domain ends with /
    domain = credentials['domain'].rstrip('/') + '/'
    
    # Create Jira extractor config
    config = JiraExtractorConfig(
        connection=ConnectionConfig(
            url=domain,
            auth=Auth(
                username=credentials['username'],
                password=credentials['password']
            )
        ),
        custom_jql=args.query,
        attributes=get_default_attributes()
    )
    
    # Create extractor
    extractor = JiraExtractor(config)
    
    # Progress callback
    def progress_hook(percent: int):
        if args.debug:
            print(f"Progress: {percent}%", file=sys.stderr)
    
    # Extract issues
    print(f"Extracting issues with JQL: {args.query}", file=sys.stderr)
    try:
        work_items = extractor.extract_all(status_hook=progress_hook, debug=args.debug)
    except Exception as e:
        print(f"Error extracting issues: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracted {len(work_items)} issues", file=sys.stderr)
    
    # Convert to CSV
    csv_content = extractor.to_csv(work_items)
    
    # Output CSV
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        print(f"CSV written to: {output_path}", file=sys.stderr)
    else:
        # Write to stdout
        sys.stdout.write(csv_content)
        sys.stdout.flush()


if __name__ == '__main__':
    main()
