"""
Jira Work Item - Represents a single Jira issue with stage durations
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from jira_types import DurationIntervals, JiraExtractorConfig


def num_to_2(n: int) -> str:
    """Pad number to 2 digits"""
    return f"0{n}" if n <= 9 else str(n)


def date_to_string(dt: datetime) -> str:
    """Format datetime to string"""
    if not dt:
        return ''
    return (
        f"{dt.year}-{num_to_2(dt.month)}-{num_to_2(dt.day)} "
        f"{num_to_2(dt.hour)}:{num_to_2(dt.minute)}:{num_to_2(dt.second)}"
    )


class JiraWorkItem:
    """Represents a Jira work item with stage duration data"""
    
    def __init__(
        self,
        id: str = '',
        stages: Dict[str, DurationIntervals] = None,
        name: str = '',
        type: str = '',
        attributes: Dict[str, str] = None
    ):
        self.id = id
        self.stages = stages or {}
        self.name = name
        self.type = type
        self.attributes = attributes or {}
    
    def to_csv(self, config: JiraExtractorConfig, stage_names: List[str]) -> List[str]:
        """
        Convert work item to CSV row
        
        Args:
            config: Extractor configuration
            stage_names: List of all stage names in order
            
        Returns:
            List of values for CSV row
        """
        base_url = config.connection.url.rstrip('/')
        line = [
            self.id,
            f"{base_url}/browse/{self.id}",
            self.name,
            self.type
        ]
        
        # Add duration days for each stage
        for stage_name in stage_names:
            if stage_name in self.stages and self.stages[stage_name].duration_days > 0:
                line.append(str(self.stages[stage_name].duration_days))
            else:
                line.append('')
        
        # Add stage start dates and recurrence count
        latest_stage_dates: List[str] = []
        stage_recurrence: List[str] = []
        
        for stage_name in stage_names:
            if stage_name not in self.stages:
                dates = []
            else:
                dates = self.stages[stage_name].from_dates or []
            
            dates_str = [date_to_string(d) for d in dates if d]
            
            # Latest date
            latest_stage_dates.append(dates_str[-1] if dates_str else '')
            # Recurrence count
            stage_recurrence.append(str(len(dates_str)) if dates_str else '')
        
        line.extend(latest_stage_dates)
        line.extend(stage_recurrence)
        
        # Add attributes in order
        for attr_key in self.attributes:
            line.append(self.attributes[attr_key])
        
        # Clean all strings
        line = [self.clean_string(s) for s in line]
        
        return line
    
    @staticmethod
    def clean_string(s: str = '') -> str:
        """Clean string for CSV output"""
        if s is None:
            s = ''
        s = str(s)
        s = (
            s.replace('"', '""')
            .replace("'", '')
            .replace(',', '-')
            .replace('\\', '')
            .strip()
        )
        return f'"{s}"'

