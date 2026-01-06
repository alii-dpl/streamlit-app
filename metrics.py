"""
Metrics Calculator for Sprint Data

This module calculates engineering metrics from Jira sprint data.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Tuple


def parse_date(date_str) -> Optional[datetime]:
    """Parse a date string to datetime, handling various formats"""
    if pd.isna(date_str) or str(date_str).strip() in ['', 'nan', 'NaT']:
        return None
    try:
        return pd.to_datetime(str(date_str).strip())
    except:
        return None


# =============================================================================
# CYCLE TIME
# =============================================================================
# What: Time from "In Progress" start → "Done/UAT/Resolved" start
# Why: Measures how fast engineering turns work into value
# Formula: Cycle Time = (Done OR UAT OR Resolved start) - In Progress start

def calculate_cycle_time(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Cycle Time for each ticket.
    
    Cycle Time = End Date - In Progress Start Date
    
    Where End Date is the earliest of:
    - Stage Done start
    - Stage UAT start  
    - Stage Resolved start
    
    Args:
        df: DataFrame with stage start columns
        
    Returns:
        Series with cycle time in days (None if not calculable)
    """
    
    def get_cycle_time(row):
        # Get In Progress start date
        in_progress_start = parse_date(row.get('Stage In Progress start'))
        if not in_progress_start:
            return None
        
        # Get end dates (Done, UAT, or Resolved - whichever came first)
        end_dates = []
        for col in ['Stage Done start', 'Stage UAT start', 'Stage Resolved start']:
            date = parse_date(row.get(col))
            if date:
                end_dates.append(date)
        
        if not end_dates:
            return None
        
        # Use the earliest end date
        end_date = min(end_dates)
        
        # Calculate cycle time in days
        if end_date >= in_progress_start:
            return (end_date - in_progress_start).total_seconds() / (24 * 3600)
        
        return None
    
    return df.apply(get_cycle_time, axis=1)


def cycle_time_stats(df: pd.DataFrame) -> dict:
    """
    Calculate cycle time statistics for a DataFrame.
    
    Args:
        df: DataFrame with 'Cycle_Time' column
        
    Returns:
        Dictionary with statistics
    """
    if 'Cycle_Time' not in df.columns:
        df = df.copy()
        df['Cycle_Time'] = calculate_cycle_time(df)
    
    valid = pd.to_numeric(df['Cycle_Time'], errors='coerce').dropna()
    
    if len(valid) == 0:
        return {
            'count': 0,
            'mean': 0,
            'median': 0,
            'p90': 0,
            'min': 0,
            'max': 0,
            'std': 0,
        }
    
    return {
        'count': len(valid),
        'mean': round(valid.mean(), 1),
        'median': round(valid.median(), 1),
        'p90': round(valid.quantile(0.90), 1),
        'min': round(valid.min(), 1),
        'max': round(valid.max(), 1),
        'std': round(valid.std(), 1),
    }


def cycle_time_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cycle time statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' and 'Cycle_Time' columns
        
    Returns:
        DataFrame with cycle time stats per type
    """
    if 'Cycle_Time' not in df.columns:
        df = df.copy()
        df['Cycle_Time'] = calculate_cycle_time(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['Cycle_Time'], errors='coerce').dropna()
        
        if len(valid) > 0:
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median': round(valid.median(), 1),
                'Mean': round(valid.mean(), 1),
                'P90': round(valid.quantile(0.90), 1),
            })
    
    return pd.DataFrame(results).sort_values('Median', ascending=True)


def identify_outliers(df: pd.DataFrame, threshold_percentile: float = 90) -> pd.DataFrame:
    """
    Identify tickets with cycle time above a threshold.
    
    Args:
        df: DataFrame with 'Cycle_Time' column
        threshold_percentile: Percentile above which to flag as outlier
        
    Returns:
        DataFrame of outlier tickets
    """
    if 'Cycle_Time' not in df.columns:
        df = df.copy()
        df['Cycle_Time'] = calculate_cycle_time(df)
    
    valid = pd.to_numeric(df['Cycle_Time'], errors='coerce')
    threshold = valid.quantile(threshold_percentile / 100)
    
    outliers = df[valid > threshold].copy()
    return outliers.sort_values('Cycle_Time', ascending=False)


def get_cycle_time_rating(median_days: float) -> Tuple[str, str]:
    """
    Get a performance rating based on median cycle time.
    
    Based on DORA metrics standards:
    - Elite: < 1 day
    - High: 1-7 days  
    - Medium: 7-30 days
    - Low: > 30 days
    
    Args:
        median_days: Median cycle time in days
        
    Returns:
        Tuple of (rating, color)
    """
    if median_days < 1:
        return 'Elite', '#22c55e'  # Green
    elif median_days <= 7:
        return 'High', '#3b82f6'   # Blue
    elif median_days <= 30:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# STAGE TIME ANALYSIS
# =============================================================================
# What: Time spent in each workflow stage
# Why: Identifies bottlenecks and slow stages in the development pipeline
# Columns: "Stage X days" columns from the CSV

# All stages to analyze (ordered by typical flow)
ALL_STAGES = [
    'New', 'Approved', 'Requirements Review', 'Product Design',
    'In Progress', 'QA Ready', 'QA', 'QA Rejected',
    'UAT', 'UAT Rejected', 'Done', 'Resolved', 'Closed',
    'Waiting on Engineering', 'Waiting on T2', 'Pending Unleash',
    'Needs Reproduction Steps', 'Review Results',
    'Obsolete', 'Duplicate', 'On Production'
]

# Stage categories for filtering
STAGE_CATEGORIES = {
    'Development': ['In Progress', 'QA Ready'],
    'QA': ['QA', 'QA Rejected'],
    'UAT': ['UAT', 'UAT Rejected'],
    'Complete': ['Done', 'Resolved', 'Closed', 'On Production'],
    'Waiting': ['Waiting on Engineering', 'Waiting on T2', 'Pending Unleash', 'Needs Reproduction Steps'],
    'Planning': ['New', 'Approved', 'Requirements Review', 'Product Design'],
}


def get_stage_time_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get summary of time spent in each stage across all tickets.
    
    Args:
        df: DataFrame with "Stage X days" columns
        
    Returns:
        DataFrame with stage time statistics
    """
    results = []
    
    for stage in ALL_STAGES:
        col = f'Stage {stage} days'
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors='coerce').dropna()
            vals = vals[vals > 0]  # Only count tickets that spent time in this stage
            
            if len(vals) > 0:
                results.append({
                    'Stage': stage,
                    'Tickets': len(vals),
                    'Total Days': round(vals.sum(), 1),
                    'Avg Days': round(vals.mean(), 2),
                    'Median Days': round(vals.median(), 2),
                    'Max Days': round(vals.max(), 1),
                })
    
    return pd.DataFrame(results).sort_values('Total Days', ascending=False) if results else pd.DataFrame()


def get_stage_time_by_ticket(df: pd.DataFrame, stages: list = None) -> pd.DataFrame:
    """
    Get time spent in each stage per ticket.
    
    Args:
        df: DataFrame with "Stage X days" columns
        stages: List of stages to include (default: all stages)
        
    Returns:
        DataFrame with stage times per ticket
    """
    if stages is None:
        stages = ALL_STAGES
    
    result_cols = ['ID', 'Name', 'Type']
    result_df = df[result_cols].copy() if all(c in df.columns for c in result_cols) else df[['ID']].copy()
    
    for stage in stages:
        col = f'Stage {stage} days'
        if col in df.columns:
            result_df[stage] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return result_df


def get_stage_time_chart_data(df: pd.DataFrame, category: str = None) -> pd.DataFrame:
    """
    Get stage time data formatted for charting (stacked bar chart).
    
    Args:
        df: DataFrame with "Stage X days" columns
        category: Filter by category ('Development', 'QA', 'UAT', 'Complete', 'Waiting', 'Planning')
                 If None, returns top stages by total time
        
    Returns:
        DataFrame with stages and their total time
    """
    if category and category in STAGE_CATEGORIES:
        stages = STAGE_CATEGORIES[category]
    else:
        stages = ALL_STAGES
    
    results = []
    for stage in stages:
        col = f'Stage {stage} days'
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors='coerce').fillna(0)
            total = vals.sum()
            count = (vals > 0).sum()
            
            if total > 0:
                results.append({
                    'Stage': stage,
                    'Total Days': round(total, 1),
                    'Avg Days': round(total / count, 2) if count > 0 else 0,
                    'Tickets': count,
                })
    
    return pd.DataFrame(results).sort_values('Total Days', ascending=False) if results else pd.DataFrame()


def get_stage_bottlenecks(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """
    Identify top bottleneck stages by average time spent.
    
    Args:
        df: DataFrame with "Stage X days" columns
        top_n: Number of top bottlenecks to return
        
    Returns:
        DataFrame with bottleneck stages
    """
    results = []
    
    for stage in ALL_STAGES:
        col = f'Stage {stage} days'
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors='coerce').dropna()
            vals = vals[vals > 0]
            
            if len(vals) >= 3:  # Only include stages with meaningful data
                results.append({
                    'Stage': stage,
                    'Avg Days': round(vals.mean(), 2),
                    'Median Days': round(vals.median(), 2),
                    'Tickets Affected': len(vals),
                    'Total Days': round(vals.sum(), 1),
                })
    
    if not results:
        return pd.DataFrame()
    
    return pd.DataFrame(results).nlargest(top_n, 'Avg Days')


def get_ticket_stage_breakdown(df: pd.DataFrame, ticket_id: str) -> pd.DataFrame:
    """
    Get detailed stage breakdown for a specific ticket.
    
    Args:
        df: DataFrame with stage columns
        ticket_id: ID of the ticket to analyze
        
    Returns:
        DataFrame with stage times for the ticket
    """
    ticket = df[df['ID'] == ticket_id]
    if ticket.empty:
        return pd.DataFrame()
    
    row = ticket.iloc[0]
    results = []
    
    for stage in ALL_STAGES:
        days_col = f'Stage {stage} days'
        start_col = f'Stage {stage} start'
        
        days = pd.to_numeric(row.get(days_col), errors='coerce') if days_col in row.index else None
        start = row.get(start_col) if start_col in row.index else None
        
        if pd.notna(days) and days > 0:
            results.append({
                'Stage': stage,
                'Days': round(days, 2),
                'Start Date': start,
            })
    
    return pd.DataFrame(results).sort_values('Days', ascending=False) if results else pd.DataFrame()


# =============================================================================
# LEAD TIME
# =============================================================================
# What: Time from "New" start → "Done/UAT/Resolved/Closed" start
# Why: Measures total delivery latency including planning overhead
# Use: Helps identify process drag before dev even starts

def calculate_lead_time(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Lead Time for each ticket.
    
    Lead Time = End Date - New Start Date
    
    Where End Date is the earliest of:
    - Stage Done start
    - Stage UAT start  
    - Stage Resolved start
    - Stage Closed start
    
    Args:
        df: DataFrame with stage start columns
        
    Returns:
        Series with lead time in days (None if not calculable)
    """
    
    def get_lead_time(row):
        # Get New start date (when ticket was created/entered system)
        new_start = parse_date(row.get('Stage New start'))
        if not new_start:
            return None
        
        # Get end dates (Done, UAT, Resolved, or Closed - whichever came first)
        end_dates = []
        for col in ['Stage Done start', 'Stage UAT start', 'Stage Resolved start', 'Stage Closed start']:
            date = parse_date(row.get(col))
            if date:
                end_dates.append(date)
        
        if not end_dates:
            return None
        
        # Use the earliest end date
        end_date = min(end_dates)
        
        # Calculate lead time in days
        if end_date >= new_start:
            return (end_date - new_start).total_seconds() / (24 * 3600)
        
        return None
    
    return df.apply(get_lead_time, axis=1)


def lead_time_stats(df: pd.DataFrame) -> dict:
    """
    Calculate lead time statistics for a DataFrame.
    
    Args:
        df: DataFrame with 'Lead_Time' column
        
    Returns:
        Dictionary with statistics
    """
    if 'Lead_Time' not in df.columns:
        df = df.copy()
        df['Lead_Time'] = calculate_lead_time(df)
    
    valid = pd.to_numeric(df['Lead_Time'], errors='coerce').dropna()
    
    if len(valid) == 0:
        return {
            'count': 0,
            'mean': 0,
            'median': 0,
            'p90': 0,
            'min': 0,
            'max': 0,
            'std': 0,
        }
    
    return {
        'count': len(valid),
        'mean': round(valid.mean(), 1),
        'median': round(valid.median(), 1),
        'p90': round(valid.quantile(0.90), 1),
        'min': round(valid.min(), 1),
        'max': round(valid.max(), 1),
        'std': round(valid.std(), 1),
    }


def lead_time_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate lead time statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' and 'Lead_Time' columns
        
    Returns:
        DataFrame with lead time stats per type
    """
    if 'Lead_Time' not in df.columns:
        df = df.copy()
        df['Lead_Time'] = calculate_lead_time(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['Lead_Time'], errors='coerce').dropna()
        
        if len(valid) > 0:
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median': round(valid.median(), 1),
                'Mean': round(valid.mean(), 1),
                'P90': round(valid.quantile(0.90), 1),
            })
    
    return pd.DataFrame(results).sort_values('Median', ascending=True)


def calculate_wait_time(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Wait Time (time before development starts).
    
    Wait Time = In Progress start - New start
    
    This is the planning/queue overhead before engineering begins.
    
    Args:
        df: DataFrame with stage start columns
        
    Returns:
        Series with wait time in days (None if not calculable)
    """
    
    def get_wait_time(row):
        new_start = parse_date(row.get('Stage New start'))
        in_progress_start = parse_date(row.get('Stage In Progress start'))
        
        if not new_start or not in_progress_start:
            return None
        
        if in_progress_start >= new_start:
            return (in_progress_start - new_start).total_seconds() / (24 * 3600)
        
        return None
    
    return df.apply(get_wait_time, axis=1)


def get_lead_time_rating(median_days: float) -> Tuple[str, str]:
    """
    Get a performance rating based on median lead time.
    
    Based on DORA metrics standards (adjusted for lead time):
    - Elite: < 3 days
    - High: 3-14 days  
    - Medium: 14-60 days
    - Low: > 60 days
    
    Args:
        median_days: Median lead time in days
        
    Returns:
        Tuple of (rating, color)
    """
    if median_days < 3:
        return 'Elite', '#22c55e'  # Green
    elif median_days <= 14:
        return 'High', '#3b82f6'   # Blue
    elif median_days <= 60:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# FLOW EFFICIENCY
# =============================================================================
# What: How much time is spent actively worked vs waiting
# Formula: Flow Efficiency = Active Time / (Active Time + Waiting Time) * 100
# Why: Identifies process bottlenecks and waste

# Define stage categories
ACTIVE_STAGES = [
    'In Progress',
    'QA',
    'UAT',
]

WAITING_STAGES = [
    'Waiting on Engineering',
    'Waiting on T2',
    'Pending Unleash',
    'Needs Reproduction Steps',
]


def calculate_flow_efficiency(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Flow Efficiency for each ticket.
    
    Flow Efficiency = Active Time / (Active Time + Waiting Time) * 100
    
    Active stages: In Progress, QA, UAT
    Waiting stages: Waiting on Engineering, Waiting on T2, Pending Unleash, Needs Reproduction Steps
    
    Args:
        df: DataFrame with "Stage X days" columns
        
    Returns:
        Series with flow efficiency percentage (0-100, None if not calculable)
    """
    
    def get_flow_efficiency(row):
        active_time = 0
        waiting_time = 0
        
        # Sum active stage days
        for stage in ACTIVE_STAGES:
            col = f'Stage {stage} days'
            if col in row.index:
                val = pd.to_numeric(row.get(col), errors='coerce')
                if pd.notna(val) and val > 0:
                    active_time += val
        
        # Sum waiting stage days
        for stage in WAITING_STAGES:
            col = f'Stage {stage} days'
            if col in row.index:
                val = pd.to_numeric(row.get(col), errors='coerce')
                if pd.notna(val) and val > 0:
                    waiting_time += val
        
        total_time = active_time + waiting_time
        
        if total_time > 0:
            return (active_time / total_time) * 100
        
        return None
    
    return df.apply(get_flow_efficiency, axis=1)


def calculate_active_time(df: pd.DataFrame) -> pd.Series:
    """Calculate total active time (In Progress + QA + UAT) for each ticket."""
    
    def get_active_time(row):
        total = 0
        for stage in ACTIVE_STAGES:
            col = f'Stage {stage} days'
            if col in row.index:
                val = pd.to_numeric(row.get(col), errors='coerce')
                if pd.notna(val) and val > 0:
                    total += val
        return total if total > 0 else None
    
    return df.apply(get_active_time, axis=1)


def calculate_waiting_time(df: pd.DataFrame) -> pd.Series:
    """Calculate total waiting time for each ticket."""
    
    def get_waiting_time(row):
        total = 0
        for stage in WAITING_STAGES:
            col = f'Stage {stage} days'
            if col in row.index:
                val = pd.to_numeric(row.get(col), errors='coerce')
                if pd.notna(val) and val > 0:
                    total += val
        return total if total > 0 else None
    
    return df.apply(get_waiting_time, axis=1)


def flow_efficiency_stats(df: pd.DataFrame) -> dict:
    """
    Calculate flow efficiency statistics for a DataFrame.
    
    Args:
        df: DataFrame with stage days columns
        
    Returns:
        Dictionary with statistics
    """
    if 'Flow_Efficiency' not in df.columns:
        df = df.copy()
        df['Flow_Efficiency'] = calculate_flow_efficiency(df)
    
    valid = pd.to_numeric(df['Flow_Efficiency'], errors='coerce').dropna()
    
    if len(valid) == 0:
        return {
            'count': 0,
            'mean': 0,
            'median': 0,
            'min': 0,
            'max': 0,
        }
    
    return {
        'count': len(valid),
        'mean': round(valid.mean(), 1),
        'median': round(valid.median(), 1),
        'min': round(valid.min(), 1),
        'max': round(valid.max(), 1),
    }


def flow_efficiency_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate flow efficiency statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and stage days columns
        
    Returns:
        DataFrame with flow efficiency stats per type
    """
    if 'Flow_Efficiency' not in df.columns:
        df = df.copy()
        df['Flow_Efficiency'] = calculate_flow_efficiency(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['Flow_Efficiency'], errors='coerce').dropna()
        
        if len(valid) > 0:
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median': round(valid.median(), 1),
                'Mean': round(valid.mean(), 1),
            })
    
    return pd.DataFrame(results).sort_values('Median', ascending=False)


def waiting_time_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get breakdown of time spent in each waiting stage.
    
    Args:
        df: DataFrame with stage days columns
        
    Returns:
        DataFrame with total days per waiting stage
    """
    results = []
    
    for stage in WAITING_STAGES:
        col = f'Stage {stage} days'
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors='coerce').fillna(0)
            total_days = vals.sum()
            ticket_count = (vals > 0).sum()
            
            if total_days > 0:
                results.append({
                    'Stage': stage,
                    'Total Days': round(total_days, 1),
                    'Tickets Affected': ticket_count,
                    'Avg Days': round(total_days / ticket_count, 1) if ticket_count > 0 else 0,
                })
    
    return pd.DataFrame(results).sort_values('Total Days', ascending=False)


def get_flow_efficiency_rating(efficiency_pct: float) -> Tuple[str, str]:
    """
    Get a performance rating based on flow efficiency percentage.
    
    - Elite: > 80%
    - High: 60-80%
    - Medium: 40-60%
    - Low: < 40%
    
    Args:
        efficiency_pct: Flow efficiency percentage (0-100)
        
    Returns:
        Tuple of (rating, color)
    """
    if efficiency_pct >= 80:
        return 'Elite', '#22c55e'  # Green
    elif efficiency_pct >= 60:
        return 'High', '#3b82f6'   # Blue
    elif efficiency_pct >= 40:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# HANDOFF DELAY
# =============================================================================
# What: Time between stage transitions that exposes handoff inefficiencies
# Two key handoffs:
#   1. Dev → QA Ready: Time from In Progress end to QA Ready start
#   2. QA Ready → QA: Time from QA Ready start to QA start
# Why: Identifies bottlenecks in team transitions and communication gaps

def calculate_dev_to_qa_ready_delay(df: pd.DataFrame) -> pd.Series:
    """
    Calculate handoff delay from Dev (In Progress) to QA Ready.
    
    This is the time between when development work is done and 
    when it's marked as ready for QA.
    
    Handoff Delay = QA Ready start - (In Progress start + In Progress days)
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Series with delay in days (None if not calculable)
    """
    from datetime import timedelta
    
    def get_delay(row):
        # Get In Progress start
        in_progress_start = parse_date(row.get('Stage In Progress start'))
        in_progress_days = pd.to_numeric(row.get('Stage In Progress days'), errors='coerce')
        
        if not in_progress_start or pd.isna(in_progress_days):
            return None
        
        # Calculate when In Progress ended
        in_progress_end = in_progress_start + timedelta(days=in_progress_days)
        
        # Get QA Ready start (or Code Review start as alternative)
        qa_ready_start = None
        for col in ['Stage QA Ready start', 'Stage Code Review start', 'Stage Ready for QA start']:
            qa_ready_start = parse_date(row.get(col))
            if qa_ready_start:
                break
        
        if not qa_ready_start:
            return None
        
        # Calculate delay (can be negative if QA Ready happened before In Progress officially ended)
        delay = (qa_ready_start - in_progress_end).total_seconds() / (24 * 3600)
        
        # Only return positive delays (negative means no handoff delay)
        return max(0, delay)
    
    return df.apply(get_delay, axis=1)


def calculate_qa_ready_to_qa_delay(df: pd.DataFrame) -> pd.Series:
    """
    Calculate handoff delay from QA Ready to QA start.
    
    This is the time a ticket waits after being marked ready for QA 
    until QA actually begins.
    
    Handoff Delay = QA start - QA Ready start
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Series with delay in days (None if not calculable)
    """
    
    def get_delay(row):
        # Get QA Ready start (try multiple possible column names)
        qa_ready_start = None
        for col in ['Stage QA Ready start', 'Stage Code Review start', 'Stage Ready for QA start']:
            qa_ready_start = parse_date(row.get(col))
            if qa_ready_start:
                break
        
        # Get QA start
        qa_start = parse_date(row.get('Stage QA start'))
        
        if not qa_ready_start or not qa_start:
            return None
        
        # Calculate delay
        delay = (qa_start - qa_ready_start).total_seconds() / (24 * 3600)
        
        # Only return positive delays
        return max(0, delay)
    
    return df.apply(get_delay, axis=1)


def calculate_total_handoff_delay(df: pd.DataFrame) -> pd.Series:
    """
    Calculate total handoff delay (Dev→QA Ready + QA Ready→QA).
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Series with total delay in days
    """
    dev_to_qa_ready = calculate_dev_to_qa_ready_delay(df).fillna(0)
    qa_ready_to_qa = calculate_qa_ready_to_qa_delay(df).fillna(0)
    
    total = dev_to_qa_ready + qa_ready_to_qa
    
    # Return None where both components were None (no delay data)
    return total.replace(0, np.nan).where(
        (dev_to_qa_ready.notna()) | (qa_ready_to_qa.notna()),
        np.nan
    ).fillna(total)


def handoff_delay_stats(df: pd.DataFrame) -> dict:
    """
    Calculate handoff delay statistics for a DataFrame.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Dictionary with statistics for each handoff type
    """
    # Calculate delays if not present
    if 'Handoff_Dev_QA_Ready' not in df.columns:
        df = df.copy()
        df['Handoff_Dev_QA_Ready'] = calculate_dev_to_qa_ready_delay(df)
    
    if 'Handoff_QA_Ready_QA' not in df.columns:
        df = df.copy()
        df['Handoff_QA_Ready_QA'] = calculate_qa_ready_to_qa_delay(df)
    
    if 'Handoff_Total' not in df.columns:
        df = df.copy()
        df['Handoff_Total'] = calculate_total_handoff_delay(df)
    
    def calc_stats(series, name):
        valid = pd.to_numeric(series, errors='coerce').dropna()
        valid = valid[valid > 0]  # Only positive delays
        
        if len(valid) == 0:
            return {
                f'{name}_count': 0,
                f'{name}_mean': 0,
                f'{name}_median': 0,
                f'{name}_p90': 0,
                f'{name}_total': 0,
            }
        
        return {
            f'{name}_count': len(valid),
            f'{name}_mean': round(valid.mean(), 1),
            f'{name}_median': round(valid.median(), 1),
            f'{name}_p90': round(valid.quantile(0.90), 1),
            f'{name}_total': round(valid.sum(), 1),
        }
    
    stats = {}
    stats.update(calc_stats(df['Handoff_Dev_QA_Ready'], 'dev_qa_ready'))
    stats.update(calc_stats(df['Handoff_QA_Ready_QA'], 'qa_ready_qa'))
    stats.update(calc_stats(df['Handoff_Total'], 'total'))
    
    return stats


def handoff_delay_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate handoff delay statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and stage columns
        
    Returns:
        DataFrame with handoff delay stats per type
    """
    if 'Handoff_Total' not in df.columns:
        df = df.copy()
        df['Handoff_Total'] = calculate_total_handoff_delay(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['Handoff_Total'], errors='coerce').dropna()
        valid = valid[valid > 0]
        
        if len(valid) > 0:
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median': round(valid.median(), 1),
                'Mean': round(valid.mean(), 1),
                'P90': round(valid.quantile(0.90), 1),
            })
    
    return pd.DataFrame(results).sort_values('Median', ascending=True) if results else pd.DataFrame()


def handoff_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get breakdown of handoff delays by transition type.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame with stats for each handoff transition
    """
    if 'Handoff_Dev_QA_Ready' not in df.columns:
        df = df.copy()
        df['Handoff_Dev_QA_Ready'] = calculate_dev_to_qa_ready_delay(df)
    
    if 'Handoff_QA_Ready_QA' not in df.columns:
        df = df.copy()
        df['Handoff_QA_Ready_QA'] = calculate_qa_ready_to_qa_delay(df)
    
    results = []
    
    handoffs = [
        ('Dev → QA Ready', 'Handoff_Dev_QA_Ready'),
        ('QA Ready → QA', 'Handoff_QA_Ready_QA'),
    ]
    
    for name, col in handoffs:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors='coerce').dropna()
            vals = vals[vals > 0]
            
            if len(vals) > 0:
                results.append({
                    'Transition': name,
                    'Total Days': round(vals.sum(), 1),
                    'Tickets Affected': len(vals),
                    'Median': round(vals.median(), 1),
                    'Mean': round(vals.mean(), 1),
                })
    
    return pd.DataFrame(results)


def get_handoff_delay_rating(median_days: float) -> Tuple[str, str]:
    """
    Get a performance rating based on median handoff delay.
    
    - Elite: < 0.5 days (< 4 hours)
    - High: 0.5-1 day
    - Medium: 1-3 days
    - Low: > 3 days
    
    Args:
        median_days: Median handoff delay in days
        
    Returns:
        Tuple of (rating, color)
    """
    if median_days < 0.5:
        return 'Elite', '#22c55e'  # Green
    elif median_days <= 1:
        return 'High', '#3b82f6'   # Blue
    elif median_days <= 3:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# RECURRENCE / REOPEN RATE (Quality & Stability KPIs)
# =============================================================================
# What: Measures how often tickets bounce back through stages
# Why: Indicates code quality, requirement clarity, and testing effectiveness
# IMPORTANT: recurrence = 1 means FIRST ENTRY (normal), recurrence > 1 means ACTUAL BOUNCE-BACK
# Columns used:
#   - Stage QA recurrence
#   - Stage UAT recurrence  
#   - Stage Rejected recurrence
# Formula: Recurrence Rate = (tickets with recurrence > 1 / total tickets) * 100

RECURRENCE_STAGES = ['QA', 'UAT', 'Rejected']


def calculate_bounce_count(df: pd.DataFrame, stage: str = None) -> pd.Series:
    """
    Calculate actual bounce-back count for each ticket.
    
    IMPORTANT: recurrence = 1 means first entry (normal flow), 
               recurrence > 1 means actual bounces (re-entered stage)
    
    Bounce count = max(0, recurrence - 1)
    
    Args:
        df: DataFrame with "Stage X recurrence" columns
        stage: Specific stage to check (e.g., 'QA', 'UAT', 'Rejected')
               If None, returns total bounces across all stages
        
    Returns:
        Series with actual bounce count per ticket (recurrence - 1)
    """
    if stage:
        col = f'Stage {stage} recurrence'
        if col in df.columns:
            recurrence = pd.to_numeric(df[col], errors='coerce').fillna(0)
            # Subtract 1 because recurrence=1 is first entry, not a bounce
            return (recurrence - 1).clip(lower=0)
        return pd.Series([0] * len(df), index=df.index)
    
    # Sum all bounce counts (recurrence - 1 for each stage)
    total = pd.Series([0.0] * len(df), index=df.index)
    for s in RECURRENCE_STAGES:
        col = f'Stage {s} recurrence'
        if col in df.columns:
            recurrence = pd.to_numeric(df[col], errors='coerce').fillna(0)
            total += (recurrence - 1).clip(lower=0)
    
    return total


def calculate_recurrence_count(df: pd.DataFrame, stage: str = None) -> pd.Series:
    """
    Alias for calculate_bounce_count - returns actual bounce count.
    
    Returns:
        Series with actual bounce count per ticket
    """
    return calculate_bounce_count(df, stage)


def calculate_recurrence_rate(df: pd.DataFrame, stage: str = None) -> float:
    """
    Calculate bounce-back rate for the dataset.
    
    Recurrence Rate = (tickets with bounces > 0 / total tickets) * 100
    
    Args:
        df: DataFrame with recurrence columns
        stage: Specific stage to check, or None for overall
        
    Returns:
        Recurrence rate as percentage (0-100)
    """
    bounces = calculate_bounce_count(df, stage)
    tickets_with_bounces = (bounces > 0).sum()
    total_tickets = len(df)
    
    if total_tickets == 0:
        return 0.0
    
    return (tickets_with_bounces / total_tickets) * 100


def recurrence_stats(df: pd.DataFrame) -> dict:
    """
    Calculate comprehensive recurrence statistics.
    
    Args:
        df: DataFrame with recurrence columns
        
    Returns:
        Dictionary with recurrence statistics
    """
    stats = {
        'total_tickets': len(df),
    }
    
    # Overall bounce count
    total_bounces = calculate_bounce_count(df)
    tickets_with_any_bounce = (total_bounces > 0).sum()
    stats['total_recurrence_count'] = int(total_bounces.sum())
    stats['tickets_with_recurrence'] = int(tickets_with_any_bounce)
    stats['overall_rate'] = round((tickets_with_any_bounce / len(df) * 100) if len(df) > 0 else 0, 1)
    stats['avg_recurrence_per_ticket'] = round(total_bounces.mean(), 2)
    
    # Per-stage breakdown
    for stage in RECURRENCE_STAGES:
        col = f'Stage {stage} recurrence'
        if col in df.columns:
            raw_recurrence = pd.to_numeric(df[col], errors='coerce').fillna(0)
            # Tickets that bounced = entered stage more than once (recurrence > 1)
            stage_bounces = (raw_recurrence - 1).clip(lower=0)
            tickets_bounced = (stage_bounces > 0).sum()
            total_stage_bounces = stage_bounces.sum()
            
            stats[f'{stage.lower()}_rate'] = round((tickets_bounced / len(df) * 100) if len(df) > 0 else 0, 1)
            stats[f'{stage.lower()}_tickets'] = int(tickets_bounced)
            stats[f'{stage.lower()}_total'] = int(total_stage_bounces)
        else:
            stats[f'{stage.lower()}_rate'] = 0.0
            stats[f'{stage.lower()}_tickets'] = 0
            stats[f'{stage.lower()}_total'] = 0
    
    return stats


def recurrence_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate recurrence statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and recurrence columns
        
    Returns:
        DataFrame with recurrence stats per type
    """
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        total_bounces = calculate_bounce_count(type_df)
        tickets_with_bounces = (total_bounces > 0).sum()
        
        if len(type_df) > 0:
            results.append({
                'Type': ticket_type,
                'Total Tickets': len(type_df),
                'With Bounces': int(tickets_with_bounces),
                'Bounce Rate': round((tickets_with_bounces / len(type_df)) * 100, 1),
                'Total Bounces': int(total_bounces.sum()),
                'Avg Bounces': round(total_bounces.mean(), 2),
            })
    
    return pd.DataFrame(results).sort_values('Bounce Rate', ascending=False) if results else pd.DataFrame()


def recurrence_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get breakdown of bounce-backs by stage type.
    
    Args:
        df: DataFrame with recurrence columns
        
    Returns:
        DataFrame with bounce stats per stage
    """
    results = []
    
    for stage in RECURRENCE_STAGES:
        col = f'Stage {stage} recurrence'
        if col in df.columns:
            raw_recurrence = pd.to_numeric(df[col], errors='coerce').fillna(0)
            bounces = (raw_recurrence - 1).clip(lower=0)
            tickets_bounced = (bounces > 0).sum()
            total_bounces = bounces.sum()
            
            if tickets_bounced > 0:
                results.append({
                    'Stage': stage,
                    'Tickets Bounced': int(tickets_bounced),
                    'Total Bounces': int(total_bounces),
                    'Bounce Rate (%)': round((tickets_bounced / len(df)) * 100, 1) if len(df) > 0 else 0,
                    'Avg Bounces/Ticket': round(total_bounces / tickets_bounced, 2),
                })
    
    return pd.DataFrame(results).sort_values('Tickets Bounced', ascending=False) if results else pd.DataFrame()


def identify_high_recurrence_tickets(df: pd.DataFrame, min_bounces: int = 1) -> pd.DataFrame:
    """
    Identify tickets with actual bounce-backs.
    
    Args:
        df: DataFrame with recurrence columns
        min_bounces: Minimum bounce count to be considered (default=1, any bounce)
        
    Returns:
        DataFrame of bounced tickets sorted by total bounces
    """
    df = df.copy()
    df['Total_Recurrence'] = calculate_bounce_count(df)
    
    # Add per-stage bounce count
    for stage in RECURRENCE_STAGES:
        col = f'Stage {stage} recurrence'
        if col in df.columns:
            raw = pd.to_numeric(df[col], errors='coerce').fillna(0)
            df[f'{stage}_Recurrence'] = (raw - 1).clip(lower=0)
        else:
            df[f'{stage}_Recurrence'] = 0
    
    bounced = df[df['Total_Recurrence'] >= min_bounces].copy()
    return bounced.sort_values('Total_Recurrence', ascending=False)


def get_recurrence_rating(rate_pct: float) -> Tuple[str, str]:
    """
    Get a performance rating based on recurrence rate.
    
    Lower is better:
    - Elite: < 5%
    - High: 5-15%
    - Medium: 15-30%
    - Low: > 30%
    
    Args:
        rate_pct: Recurrence rate percentage (0-100)
        
    Returns:
        Tuple of (rating, color)
    """
    if rate_pct < 5:
        return 'Elite', '#22c55e'  # Green
    elif rate_pct <= 15:
        return 'High', '#3b82f6'   # Blue
    elif rate_pct <= 30:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# DEFECT ESCAPE RATE (Quality & Stability KPIs)
# =============================================================================
# What: Issues that reach UAT/Production then move back to QA Rejected/In Progress
# Why: Shows how many defects escape QA testing
# Logic: A defect "escaped" if it:
#   1. Reached UAT or Production (has UAT/Done start date)
#   2. Then bounced back (recurrence > 1 means re-entered stage after leaving)
# IMPORTANT: recurrence = 1 means first entry, recurrence > 1 means actual bounce-back
# Formula: Escape Rate = (escaped defects / total tickets that reached UAT+) * 100

# Stages that indicate ticket reached late stages
LATE_STAGES = ['UAT', 'Done', 'Resolved', 'Closed']

# Stages where bounce-back indicates defect escape
ESCAPE_BOUNCE_STAGES = ['Rejected', 'QA', 'In Progress']


def is_defect_escape(row) -> bool:
    """
    Determine if a ticket represents a defect escape.
    
    A defect escape occurs when:
    1. Ticket reached UAT or later stages (UAT, Done, Production)
    2. Ticket bounced back (recurrence > 1, meaning re-entered a stage)
    
    Note: recurrence = 1 is first entry (normal), recurrence > 1 is actual bounce-back
    
    Args:
        row: DataFrame row
        
    Returns:
        True if ticket is a defect escape
    """
    # Check if ticket reached late stages (UAT or beyond)
    reached_late_stage = False
    for stage in LATE_STAGES:
        start_col = f'Stage {stage} start'
        days_col = f'Stage {stage} days'
        if start_col in row.index:
            if pd.notna(row.get(start_col)):
                reached_late_stage = True
                break
        if days_col in row.index:
            days = pd.to_numeric(row.get(days_col), errors='coerce')
            if pd.notna(days) and days > 0:
                reached_late_stage = True
                break
    
    if not reached_late_stage:
        return False
    
    # Check if ticket bounced back after reaching late stage
    # recurrence > 1 means re-entered stage (actual bounce-back)
    for stage in ESCAPE_BOUNCE_STAGES:
        col = f'Stage {stage} recurrence'
        if col in row.index:
            val = pd.to_numeric(row.get(col), errors='coerce')
            # recurrence > 1 means bounced back (re-entered after leaving)
            if pd.notna(val) and val > 1:
                return True
    
    return False


def calculate_defect_escape(df: pd.DataFrame) -> pd.Series:
    """
    Calculate whether each ticket is a defect escape.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Series of booleans (True = defect escape)
    """
    return df.apply(is_defect_escape, axis=1)


def defect_escape_stats(df: pd.DataFrame) -> dict:
    """
    Calculate defect escape statistics.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Dictionary with escape statistics
    """
    # Calculate escapes
    df = df.copy()
    df['Is_Escape'] = calculate_defect_escape(df)
    
    # Count tickets that reached late stages (UAT+)
    def reached_late_stage(row):
        for stage in LATE_STAGES:
            start_col = f'Stage {stage} start'
            days_col = f'Stage {stage} days'
            if start_col in row.index and pd.notna(row.get(start_col)):
                return True
            if days_col in row.index:
                days = pd.to_numeric(row.get(days_col), errors='coerce')
                if pd.notna(days) and days > 0:
                    return True
        return False
    
    df['Reached_Late_Stage'] = df.apply(reached_late_stage, axis=1)
    
    total_tickets = len(df)
    tickets_reached_late = df['Reached_Late_Stage'].sum()
    escaped_defects = df['Is_Escape'].sum()
    
    # Escape rate based on tickets that reached late stages
    escape_rate_of_late = (escaped_defects / tickets_reached_late * 100) if tickets_reached_late > 0 else 0
    # Overall escape rate
    overall_escape_rate = (escaped_defects / total_tickets * 100) if total_tickets > 0 else 0
    
    return {
        'total_tickets': total_tickets,
        'tickets_reached_uat': int(tickets_reached_late),
        'escaped_defects': int(escaped_defects),
        'escape_rate': round(escape_rate_of_late, 1),  # % of UAT+ tickets that escaped
        'overall_rate': round(overall_escape_rate, 1),  # % of all tickets
    }


def defect_escape_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate defect escape statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and stage columns
        
    Returns:
        DataFrame with escape stats per type
    """
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    df = df.copy()
    df['Is_Escape'] = calculate_defect_escape(df)
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        total = len(type_df)
        escapes = type_df['Is_Escape'].sum()
        
        if total > 0:
            results.append({
                'Type': ticket_type,
                'Total Tickets': total,
                'Escaped': int(escapes),
                'Escape Rate': round((escapes / total) * 100, 1),
            })
    
    return pd.DataFrame(results).sort_values('Escape Rate', ascending=False) if results else pd.DataFrame()


def defect_escape_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get breakdown of where defects were caught (which stage sent them back).
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame showing which stages caught the escaped defects
    """
    df = df.copy()
    df['Is_Escape'] = calculate_defect_escape(df)
    
    # Only look at escaped tickets
    escaped_df = df[df['Is_Escape']].copy()
    
    if len(escaped_df) == 0:
        return pd.DataFrame()
    
    results = []
    
    # Check which indicator caught the defect
    indicators = [
        ('Rejected (after UAT)', 'Stage Rejected recurrence'),
        ('QA (re-test)', 'Stage QA recurrence'),
        ('In Progress (rework)', 'Stage In Progress recurrence'),
    ]
    
    for name, col in indicators:
        if col in escaped_df.columns:
            vals = pd.to_numeric(escaped_df[col], errors='coerce').fillna(0)
            caught_count = (vals > 0).sum()
            
            if caught_count > 0:
                results.append({
                    'Caught At': name,
                    'Tickets': int(caught_count),
                    'Percentage': round((caught_count / len(escaped_df)) * 100, 1),
                })
    
    return pd.DataFrame(results).sort_values('Tickets', ascending=False) if results else pd.DataFrame()


def identify_escaped_defects(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify all tickets that are defect escapes.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame of escaped defect tickets
    """
    df = df.copy()
    df['Is_Escape'] = calculate_defect_escape(df)
    
    # Add escape indicator columns for display (safely handle missing columns)
    col_rejected = 'Stage Rejected recurrence'
    col_qa = 'Stage QA recurrence'
    col_in_progress = 'Stage In Progress recurrence'
    
    df['Rejected_After_UAT'] = pd.to_numeric(df[col_rejected], errors='coerce').fillna(0) if col_rejected in df.columns else 0
    df['QA_Retest'] = pd.to_numeric(df[col_qa], errors='coerce').fillna(0) if col_qa in df.columns else 0
    df['Rework'] = pd.to_numeric(df[col_in_progress], errors='coerce').fillna(0) if col_in_progress in df.columns else 0
    
    escaped = df[df['Is_Escape']].copy()
    return escaped.sort_values(['Rejected_After_UAT', 'QA_Retest', 'Rework'], ascending=False)


def get_escape_rate_rating(rate_pct: float) -> Tuple[str, str]:
    """
    Get a performance rating based on defect escape rate.
    
    Lower is better (measures QA effectiveness):
    - Elite: < 2%
    - High: 2-5%
    - Medium: 5-15%
    - Low: > 15%
    
    Args:
        rate_pct: Defect escape rate percentage (0-100)
        
    Returns:
        Tuple of (rating, color)
    """
    if rate_pct < 2:
        return 'Elite', '#22c55e'  # Green
    elif rate_pct <= 5:
        return 'High', '#3b82f6'   # Blue
    elif rate_pct <= 15:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# ESTIMATION ACCURACY (Team Maturity KPI)
# =============================================================================
# What: Measures how well teams estimate their work
# Formula: Estimation Accuracy = Actual Time / Estimated Time
# Where:
#   - Estimated Time = Story Points × 8 hours (1 SP = 1 day = 8 hours)
#   - Actual Time = Time from "In Progress start" to "UAT start" (in hours)
# Why: Identifies under/over estimation trends and team maturity

def calculate_estimation_accuracy(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Estimation Accuracy for each ticket.
    
    Estimation Accuracy = Actual Hours / Estimated Hours
    
    Where:
    - Estimated Hours = Story Points × 8 (assuming 1 SP = 1 day = 8 hours)
    - Actual Hours = Time from In Progress start to UAT start
    
    Result interpretation:
    - 1.0 = Perfect estimation
    - < 1.0 = Overestimated (finished faster than expected)
    - > 1.0 = Underestimated (took longer than expected)
    
    Args:
        df: DataFrame with StoryPoints and stage columns
        
    Returns:
        Series with estimation accuracy ratio (None if not calculable)
    """
    
    def get_estimation_accuracy(row):
        # Get estimated hours from Story Points (1 SP = 8 hours)
        story_points = pd.to_numeric(row.get('StoryPoints'), errors='coerce')
        if pd.isna(story_points) or story_points <= 0:
            return None
        
        estimated_hours = story_points * 8  # 1 SP = 8 hours of work
        
        # Get actual time: In Progress start → UAT start
        in_progress_start = parse_date(row.get('Stage In Progress start'))
        if not in_progress_start:
            return None
        
        # Get UAT start (or Done/Resolved as fallback)
        end_date = None
        for col in ['Stage UAT start', 'Stage Done start', 'Stage Resolved start']:
            date = parse_date(row.get(col))
            if date:
                if end_date is None or date < end_date:
                    end_date = date
        
        if not end_date or end_date <= in_progress_start:
            return None
        
        # Calculate actual hours (using calendar time, convert to work hours)
        # Approximate: total days × 8 hours/day (simpler than counting business days)
        actual_days = (end_date - in_progress_start).total_seconds() / (24 * 3600)
        actual_hours = actual_days * 8  # Convert calendar days to work hours (rough approximation)
        
        if actual_hours <= 0 or estimated_hours <= 0:
            return None
        
        return actual_hours / estimated_hours
    
    return df.apply(get_estimation_accuracy, axis=1)


def estimation_accuracy_stats(df: pd.DataFrame) -> dict:
    """
    Calculate estimation accuracy statistics.
    
    Args:
        df: DataFrame with time columns
        
    Returns:
        Dictionary with estimation statistics
    """
    if 'Estimation_Accuracy' not in df.columns:
        df = df.copy()
        df['Estimation_Accuracy'] = calculate_estimation_accuracy(df)
    
    valid = pd.to_numeric(df['Estimation_Accuracy'], errors='coerce').dropna()
    valid = valid[valid > 0]  # Filter out invalid values
    
    if len(valid) == 0:
        return {
            'count': 0,
            'mean': 0,
            'median': 0,
            'std': 0,
            'overestimated_count': 0,
            'underestimated_count': 0,
            'accurate_count': 0,
            'overestimated_pct': 0,
            'underestimated_pct': 0,
            'accurate_pct': 0,
        }
    
    # Count estimation categories
    # Accurate: 0.8 - 1.2 (within 20%)
    # Overestimated: < 0.8 (finished faster)
    # Underestimated: > 1.2 (took longer)
    accurate = ((valid >= 0.8) & (valid <= 1.2)).sum()
    overestimated = (valid < 0.8).sum()
    underestimated = (valid > 1.2).sum()
    
    total = len(valid)
    
    return {
        'count': total,
        'mean': round(valid.mean(), 2),
        'median': round(valid.median(), 2),
        'std': round(valid.std(), 2),
        'overestimated_count': int(overestimated),
        'underestimated_count': int(underestimated),
        'accurate_count': int(accurate),
        'overestimated_pct': round((overestimated / total) * 100, 1),
        'underestimated_pct': round((underestimated / total) * 100, 1),
        'accurate_pct': round((accurate / total) * 100, 1),
    }


def estimation_accuracy_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate estimation accuracy statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and time columns
        
    Returns:
        DataFrame with estimation stats per type
    """
    if 'Estimation_Accuracy' not in df.columns:
        df = df.copy()
        df['Estimation_Accuracy'] = calculate_estimation_accuracy(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['Estimation_Accuracy'], errors='coerce').dropna()
        valid = valid[valid > 0]
        
        if len(valid) > 0:
            accurate = ((valid >= 0.8) & (valid <= 1.2)).sum()
            underestimated = (valid > 1.2).sum()
            
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median': round(valid.median(), 2),
                'Mean': round(valid.mean(), 2),
                'Accurate %': round((accurate / len(valid)) * 100, 1),
                'Underestimated %': round((underestimated / len(valid)) * 100, 1),
            })
    
    return pd.DataFrame(results).sort_values('Median', ascending=True) if results else pd.DataFrame()


def identify_estimation_outliers(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """
    Identify tickets with significant estimation errors.
    
    Args:
        df: DataFrame with time columns
        threshold: Ratio threshold for outliers (default 2.0 = took 2x longer)
        
    Returns:
        DataFrame of outlier tickets sorted by estimation accuracy
    """
    if 'Estimation_Accuracy' not in df.columns:
        df = df.copy()
        df['Estimation_Accuracy'] = calculate_estimation_accuracy(df)
    
    valid_df = df[df['Estimation_Accuracy'].notna()].copy()
    valid_df = valid_df[valid_df['Estimation_Accuracy'] > 0]
    
    # Filter outliers (either severely under or over estimated)
    outliers = valid_df[(valid_df['Estimation_Accuracy'] > threshold) | 
                        (valid_df['Estimation_Accuracy'] < 1/threshold)]
    
    return outliers.sort_values('Estimation_Accuracy', ascending=False)


def get_estimation_accuracy_rating(median_accuracy: float) -> Tuple[str, str]:
    """
    Get a performance rating based on median estimation accuracy.
    
    Closer to 1.0 is better:
    - Elite: 0.9 - 1.1 (within 10%)
    - High: 0.8 - 1.2 (within 20%)
    - Medium: 0.6 - 1.5 (within 40-50%)
    - Low: outside these ranges
    
    Args:
        median_accuracy: Median estimation accuracy ratio
        
    Returns:
        Tuple of (rating, color)
    """
    if 0.9 <= median_accuracy <= 1.1:
        return 'Elite', '#22c55e'  # Green
    elif 0.8 <= median_accuracy <= 1.2:
        return 'High', '#3b82f6'   # Blue
    elif 0.6 <= median_accuracy <= 1.5:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


def format_time_seconds(seconds: float) -> str:
    """
    Format seconds into human-readable time string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m", "1d 4h")
    """
    if pd.isna(seconds) or seconds <= 0:
        return "—"
    
    hours = seconds / 3600
    
    if hours < 1:
        return f"{int(seconds / 60)}m"
    elif hours < 24:
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        days = hours / 8  # Assume 8-hour workday
        d = int(days)
        h = int((days - d) * 8)
        return f"{d}d {h}h" if h > 0 else f"{d}d"
