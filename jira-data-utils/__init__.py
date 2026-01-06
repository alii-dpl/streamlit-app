"""
Jira Data Python - Python version of the Jira Lead/Cycle Time Extractor

This package extracts Jira issues and calculates stage durations for
lead time, cycle time, and DORA metrics analysis.
"""
import sys
from pathlib import Path

# Ensure the package directory is in the path
pkg_dir = Path(__file__).parent
if str(pkg_dir) not in sys.path:
    sys.path.insert(0, str(pkg_dir))

from jira_types import JiraExtractorConfig, Auth, ConnectionConfig
from extractor import JiraExtractor
from components.yaml_converter import load_yaml_config, convert_yaml_to_jira_settings

__version__ = '1.0.0'

__all__ = [
    'JiraExtractor',
    'JiraExtractorConfig',
    'Auth',
    'ConnectionConfig',
    'load_yaml_config',
    'convert_yaml_to_jira_settings',
]
