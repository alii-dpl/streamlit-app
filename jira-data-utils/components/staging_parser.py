"""
Staging Parser - Parse changelog and calculate stage durations
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from jira_types import (
    ChangelogRow,
    ChangelogRowDuration,
    DurationInterval,
    DurationIntervals,
    JiraApiIssue,
)


def to_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string to datetime"""
    if not date_str:
        return None
    try:
        # Handle various ISO formats
        date_str = date_str.replace('Z', '+00:00')
        if '.' in date_str:
            # Remove microseconds precision beyond 6 digits
            parts = date_str.split('.')
            if len(parts) == 2:
                tz_part = ''
                frac_part = parts[1]
                for i, c in enumerate(frac_part):
                    if not c.isdigit():
                        tz_part = frac_part[i:]
                        frac_part = frac_part[:i]
                        break
                frac_part = frac_part[:6]
                date_str = f"{parts[0]}.{frac_part}{tz_part}"
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def round_2dec(num: float) -> Optional[float]:
    """Round to 1 decimal place"""
    return round(num, 1) if num is not None else None


def date_diff_days(from_date: datetime, to_date: datetime) -> Optional[float]:
    """Calculate difference between dates in days"""
    if not from_date or not to_date:
        return None
    
    diff_seconds = (to_date - from_date).total_seconds()
    
    # More than 1 minute
    if diff_seconds > 60:
        return round_2dec(diff_seconds / (24 * 3600))
    return None


def to_changelog_row_duration(
    from_date: datetime,
    to_date: datetime,
    from_value: str
) -> ChangelogRowDuration:
    """Create a changelog row duration"""
    diff_days = date_diff_days(from_date, to_date)
    
    duration_interval = DurationInterval(
        from_date=from_date,
        to_date=to_date,
        duration_days=diff_days
    )
    
    return ChangelogRowDuration(
        from_value=from_value,
        duration_interval=duration_interval
    )


def populate_stages(issue: JiraApiIssue) -> Dict[str, DurationIntervals]:
    """
    Parse issue changelog and calculate time spent in each stage
    
    Args:
        issue: Jira issue with changelog
        
    Returns:
        Dictionary mapping stage names to their duration intervals
    """
    now = datetime.now(timezone.utc)
    changelog: List[ChangelogRow] = []
    
    # 1. Extract status changes from changelog
    histories = issue.get('changelog', {}).get('histories', [])
    
    for history in histories:
        created = history.get('created')
        items = history.get('items', [])
        
        for item in items:
            if item.get('field') == 'status':
                row = ChangelogRow(
                    from_value=item.get('fromString'),
                    to_value=item.get('toString'),
                    created=created
                )
                changelog.append(row)
    
    # 2. Sort by created date
    changelog.sort(key=lambda x: x.created or '')
    
    # 3. Calculate durations
    row_durations: List[ChangelogRowDuration] = []
    
    fields = issue.get('fields', {})
    issue_created = fields.get('created')
    
    for i, row in enumerate(changelog):
        if i == 0:
            from_date = to_date(issue_created)
        else:
            from_date = to_date(changelog[i - 1].created)
        
        rd = to_changelog_row_duration(
            from_date,
            to_date(row.created),
            row.from_value
        )
        row_durations.append(rd)
    
    # 4. Handle current/tailing status
    current_status = fields.get('status', {}).get('name', '')
    
    if len(changelog) == 0:
        # No status changes - ticket has been in initial status
        current_rd = to_changelog_row_duration(
            to_date(issue_created),
            now,
            current_status
        )
        row_durations.append(current_rd)
    else:
        # Add duration for current status
        last_date = row_durations[-1].duration_interval.to_date if row_durations else to_date(issue_created)
        current_rd = to_changelog_row_duration(
            last_date,
            now,
            current_status
        )
        row_durations.append(current_rd)
    
    # 5. Build status map
    status_map: Dict[str, DurationIntervals] = {}
    
    for rd in row_durations:
        status = rd.from_value
        if not status:
            continue
            
        interval = rd.duration_interval
        
        if status in status_map:
            existing = status_map[status]
            existing.from_dates.append(interval.from_date)
            existing.to_dates.append(interval.to_date)
            existing.duration_days += interval.duration_days or 0
        else:
            status_map[status] = DurationIntervals(
                from_dates=[interval.from_date] if interval.from_date else [],
                to_dates=[interval.to_date] if interval.to_date else [],
                duration_days=interval.duration_days or 0
            )
    
    return status_map

