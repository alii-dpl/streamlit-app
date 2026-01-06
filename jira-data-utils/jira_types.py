"""
Type definitions for Jira Data Extractor
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class Auth:
    """Authentication configuration"""
    username: Optional[str] = None
    password: Optional[str] = None
    oauth: Optional[Dict[str, str]] = None


@dataclass
class ConnectionConfig:
    """Connection configuration"""
    url: Optional[str] = None
    auth: Optional[Auth] = None


@dataclass
class JiraExtractorConfig:
    """Main extractor configuration"""
    connection: Optional[ConnectionConfig] = None
    batch_size: int = 25
    custom_jql: Optional[str] = None
    attributes: Optional[Dict[str, str]] = None
    output_file: Optional[str] = None


@dataclass
class DurationInterval:
    """Single duration interval"""
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    duration_days: Optional[float] = None


@dataclass
class DurationIntervals:
    """Multiple duration intervals for a stage"""
    from_dates: List[datetime] = field(default_factory=list)
    to_dates: List[datetime] = field(default_factory=list)
    duration_days: float = 0.0


@dataclass
class ChangelogRow:
    """Single changelog entry"""
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    created: Optional[str] = None


@dataclass
class ChangelogRowDuration:
    """Changelog row with duration"""
    from_value: Optional[str] = None
    duration_interval: Optional[DurationInterval] = None


# Type aliases for Jira API responses
JiraApiIssue = Dict[str, Any]
JiraApiIssueQueryResponse = Dict[str, Any]

