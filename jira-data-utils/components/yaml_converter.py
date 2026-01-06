"""
YAML Converter - Load and convert YAML config to JiraExtractorConfig
"""
from typing import Any, Dict
import yaml
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from jira_types import Auth, ConnectionConfig, JiraExtractorConfig


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """Load YAML configuration file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def convert_yaml_to_jira_settings(config: Dict[str, Any]) -> JiraExtractorConfig:
    """
    Convert YAML config dictionary to JiraExtractorConfig
    
    Args:
        config: Parsed YAML configuration
        
    Returns:
        JiraExtractorConfig object
    """
    connection_yaml = config.get('Connection', {})
    jql_yaml = config.get('JQL', {})
    
    auth = Auth(
        username=connection_yaml.get('Username'),
        password=connection_yaml.get('Password'),
        oauth=None  # OAuth support can be added if needed
    )
    
    connection = ConnectionConfig(
        url=connection_yaml.get('Domain'),
        auth=auth
    )
    
    return JiraExtractorConfig(
        connection=connection,
        batch_size=config.get('BatchSize', 25),
        custom_jql=jql_yaml.get('Query'),
        attributes=config.get('Attributes', {}),
        output_file=config.get('OutPutFileName')
    )

