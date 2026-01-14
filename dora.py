"""
DORA Metrics Calculator for Sprint Data

This module calculates DORA (DevOps Research and Assessment) metrics from Jira sprint data.

DORA Metrics:
1. Deployment Frequency (DF) - How often you deploy to production
2. Lead Time for Changes (LTC) - Time from commit to production
3. Change Failure Rate (CFR) - Percentage of deployments causing failures
4. Mean Time to Recovery (MTTR) - How quickly you recover from failures
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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
# DEPLOYMENT FREQUENCY (DF)
# =============================================================================
# What: How often you deploy to production
# From Jira: Count issues entering "Stage On Production"
# Why: Higher deployment frequency correlates with better software delivery performance
# 
# Benchmarks (from DORA research):
#   - Elite: On-demand / multiple times per day
#   - High: Weekly to daily
#   - Medium: Monthly to weekly
#   - Low: Less than monthly (quarterly or less)

def count_deployments(df: pd.DataFrame) -> int:
    """
    Count total deployments to production.
    
    A deployment is counted when a ticket has:
    - Stage On Production days > 0, OR
    - Stage On Production start date exists
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Number of deployments
    """
    count = 0
    
    # Check for "On Production" stage
    if 'Stage On Production days' in df.columns:
        prod_days = pd.to_numeric(df['Stage On Production days'], errors='coerce').fillna(0)
        count = (prod_days > 0).sum()
    elif 'Stage On Production start' in df.columns:
        prod_start = df['Stage On Production start'].apply(parse_date)
        count = prod_start.notna().sum()
    
    return int(count)


def get_deployments(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get all tickets that were deployed to production.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame of deployed tickets
    """
    mask = pd.Series([False] * len(df), index=df.index)
    
    if 'Stage On Production days' in df.columns:
        prod_days = pd.to_numeric(df['Stage On Production days'], errors='coerce').fillna(0)
        mask = mask | (prod_days > 0)
    
    if 'Stage On Production start' in df.columns:
        prod_start = df['Stage On Production start'].apply(parse_date)
        mask = mask | prod_start.notna()
    
    return df[mask].copy()


def calculate_deployment_frequency(df: pd.DataFrame, sprint_duration_days: int = 14) -> dict:
    """
    Calculate Deployment Frequency metrics.
    
    Args:
        df: DataFrame with stage columns
        sprint_duration_days: Number of days in the sprint (default 14 for 2-week sprint)
        
    Returns:
        Dictionary with deployment frequency metrics
    """
    deployments = count_deployments(df)
    
    # Calculate frequency per time period
    deployments_per_day = deployments / sprint_duration_days if sprint_duration_days > 0 else 0
    deployments_per_week = deployments_per_day * 7
    deployments_per_month = deployments_per_day * 30
    
    return {
        'total_deployments': deployments,
        'sprint_duration_days': sprint_duration_days,
        'deployments_per_day': round(deployments_per_day, 2),
        'deployments_per_week': round(deployments_per_week, 1),
        'deployments_per_month': round(deployments_per_month, 1),
        'total_tickets': len(df),
        'deployment_percentage': round((deployments / len(df) * 100) if len(df) > 0 else 0, 1),
    }


def deployment_frequency_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate deployment frequency grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and stage columns
        
    Returns:
        DataFrame with deployment stats per type
    """
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        deployed = count_deployments(type_df)
        total = len(type_df)
        
        if total > 0:
            results.append({
                'Type': ticket_type,
                'Total Tickets': total,
                'Deployed': deployed,
                'Deployment Rate': round((deployed / total) * 100, 1),
            })
    
    return pd.DataFrame(results).sort_values('Deployed', ascending=False) if results else pd.DataFrame()


def deployment_frequency_by_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get deployments grouped by date for trend analysis.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame with deployments per date
    """
    if 'Stage On Production start' not in df.columns:
        return pd.DataFrame()
    
    # Parse production start dates
    df_temp = df.copy()
    df_temp['_prod_date'] = df_temp['Stage On Production start'].apply(parse_date)
    
    # Filter to tickets with production dates
    deployed = df_temp[df_temp['_prod_date'].notna()].copy()
    
    if len(deployed) == 0:
        return pd.DataFrame()
    
    # Group by date
    deployed['_date'] = deployed['_prod_date'].dt.date
    daily_counts = deployed.groupby('_date').size().reset_index(name='Deployments')
    daily_counts.columns = ['Date', 'Deployments']
    daily_counts = daily_counts.sort_values('Date')
    
    # Add cumulative sum
    daily_counts['Cumulative'] = daily_counts['Deployments'].cumsum()
    
    return daily_counts


def deployment_frequency_by_week(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get deployments grouped by week for trend analysis.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame with deployments per week
    """
    if 'Stage On Production start' not in df.columns:
        return pd.DataFrame()
    
    # Parse production start dates
    df_temp = df.copy()
    df_temp['_prod_date'] = df_temp['Stage On Production start'].apply(parse_date)
    
    # Filter to tickets with production dates
    deployed = df_temp[df_temp['_prod_date'].notna()].copy()
    
    if len(deployed) == 0:
        return pd.DataFrame()
    
    # Group by week
    deployed['_week'] = deployed['_prod_date'].dt.to_period('W').astype(str)
    weekly_counts = deployed.groupby('_week').size().reset_index(name='Deployments')
    weekly_counts.columns = ['Week', 'Deployments']
    weekly_counts = weekly_counts.sort_values('Week')
    
    return weekly_counts


def get_deployment_frequency_rating(deployments_per_week: float) -> Tuple[str, str]:
    """
    Get DORA performance rating based on deployment frequency.
    
    Based on DORA research benchmarks:
    - Elite: On-demand / multiple per day (>7 per week)
    - High: Daily to weekly (1-7 per week)
    - Medium: Weekly to monthly (0.25-1 per week)
    - Low: Less than monthly (<0.25 per week)
    
    Args:
        deployments_per_week: Average deployments per week
        
    Returns:
        Tuple of (rating, color)
    """
    if deployments_per_week >= 7:
        return 'Elite', '#22c55e'  # Green - Multiple per day
    elif deployments_per_week >= 1:
        return 'High', '#3b82f6'   # Blue - Daily to weekly
    elif deployments_per_week >= 0.25:
        return 'Medium', '#f59e0b' # Orange - Weekly to monthly
    else:
        return 'Low', '#ef4444'    # Red - Less than monthly


# =============================================================================
# LEAD TIME FOR CHANGES (LTC)
# =============================================================================
# What: Time from code commit to running in production
# From Jira: Time from "In Progress start" to "On Production start"
# Why: Measures the velocity of your deployment pipeline
#
# Benchmarks (from DORA research):
#   - Elite: Less than 1 hour
#   - High: 1 day to 1 week
#   - Medium: 1 week to 1 month
#   - Low: More than 1 month

def calculate_lead_time_for_changes(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Lead Time for Changes for each ticket.
    
    Lead Time for Changes = On Production start - In Progress start
    
    This measures the time from when development begins to when code 
    reaches production.
    
    Args:
        df: DataFrame with stage start columns
        
    Returns:
        Series with lead time in days (None if not calculable)
    """
    
    def get_ltc(row):
        # Get In Progress start date (when dev started)
        in_progress_start = parse_date(row.get('Stage In Progress start'))
        if not in_progress_start:
            return None
        
        # Get On Production start date (when deployed)
        on_production_start = parse_date(row.get('Stage On Production start'))
        if not on_production_start:
            return None
        
        # Calculate lead time in days
        if on_production_start >= in_progress_start:
            return (on_production_start - in_progress_start).total_seconds() / (24 * 3600)
        
        return None
    
    return df.apply(get_ltc, axis=1)


def lead_time_for_changes_stats(df: pd.DataFrame) -> dict:
    """
    Calculate Lead Time for Changes statistics.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Dictionary with statistics
    """
    if 'Lead_Time_Changes' not in df.columns:
        df = df.copy()
        df['Lead_Time_Changes'] = calculate_lead_time_for_changes(df)
    
    valid = pd.to_numeric(df['Lead_Time_Changes'], errors='coerce').dropna()
    
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


def lead_time_for_changes_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Lead Time for Changes statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' and stage columns
        
    Returns:
        DataFrame with lead time stats per type
    """
    if 'Lead_Time_Changes' not in df.columns:
        df = df.copy()
        df['Lead_Time_Changes'] = calculate_lead_time_for_changes(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['Lead_Time_Changes'], errors='coerce').dropna()
        
        if len(valid) > 0:
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median': round(valid.median(), 1),
                'Mean': round(valid.mean(), 1),
                'P90': round(valid.quantile(0.90), 1),
            })
    
    return pd.DataFrame(results).sort_values('Median', ascending=True) if results else pd.DataFrame()


def get_lead_time_for_changes_rating(median_days: float) -> Tuple[str, str]:
    """
    Get DORA performance rating based on Lead Time for Changes.
    
    Based on DORA research benchmarks:
    - Elite: Less than 1 day (ideally less than 1 hour)
    - High: 1 day to 1 week
    - Medium: 1 week to 1 month
    - Low: More than 1 month
    
    Args:
        median_days: Median lead time in days
        
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
# CHANGE FAILURE RATE (CFR)
# =============================================================================
# What: Percentage of deployments causing incidents / rework
# From Jira: QA Rejected, UAT Rejected, Bugs after Production
# Formula: CFR = (QA_recurrence + UAT_recurrence) / Deployments
# Why: Measures the quality of releases
#
# Benchmarks:
#   - Elite: 0-15%
#   - Medium: 16-30%
#   - Low: > 30%

def calculate_failure_signals(row) -> int:
    """
    Calculate failure signals for a ticket (QA + UAT recurrence).
    
    Failure signals are the sum of:
    - Stage QA recurrence (times ticket went back to QA)
    - Stage UAT recurrence (times ticket went back to UAT)
    
    Note: recurrence = 1 means first entry (normal), recurrence > 1 means bounce-back
    We count total recurrence values as failure signals.
    
    Args:
        row: DataFrame row
        
    Returns:
        Total failure signals count
    """
    total = 0
    
    # QA recurrence
    qa_col = 'Stage QA recurrence'
    if qa_col in row.index:
        qa_rec = pd.to_numeric(row.get(qa_col), errors='coerce')
        if pd.notna(qa_rec) and qa_rec > 1:
            # Count bounces (recurrence - 1, since 1 is first entry)
            total += int(qa_rec - 1)
    
    # UAT recurrence
    uat_col = 'Stage UAT recurrence'
    if uat_col in row.index:
        uat_rec = pd.to_numeric(row.get(uat_col), errors='coerce')
        if pd.notna(uat_rec) and uat_rec > 1:
            # Count bounces (recurrence - 1, since 1 is first entry)
            total += int(uat_rec - 1)
    
    # QA Rejected recurrence
    qa_rej_col = 'Stage QA Rejected recurrence'
    if qa_rej_col in row.index:
        qa_rej_rec = pd.to_numeric(row.get(qa_rej_col), errors='coerce')
        if pd.notna(qa_rej_rec) and qa_rej_rec > 0:
            total += int(qa_rej_rec)
    
    # UAT Rejected recurrence
    uat_rej_col = 'Stage UAT Rejected recurrence'
    if uat_rej_col in row.index:
        uat_rej_rec = pd.to_numeric(row.get(uat_rej_col), errors='coerce')
        if pd.notna(uat_rej_rec) and uat_rej_rec > 0:
            total += int(uat_rej_rec)
    
    return total


def calculate_change_failure_rate(df: pd.DataFrame) -> dict:
    """
    Calculate Change Failure Rate metrics.
    
    Formula: CFR = (QA_recurrence + UAT_recurrence) / Deployments
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Dictionary with CFR metrics
    """
    # Count total deployments
    total_deployments = count_deployments(df)
    
    if total_deployments == 0:
        return {
            'total_deployments': 0,
            'total_failure_signals': 0,
            'qa_recurrence_total': 0,
            'uat_recurrence_total': 0,
            'change_failure_rate': 0,
            'tickets_with_failures': 0,
        }
    
    # Calculate failure signals for each ticket
    df_temp = df.copy()
    df_temp['_failure_signals'] = df_temp.apply(calculate_failure_signals, axis=1)
    
    # Sum all failure signals
    total_failure_signals = df_temp['_failure_signals'].sum()
    tickets_with_failures = (df_temp['_failure_signals'] > 0).sum()
    
    # Calculate individual recurrence totals
    qa_total = 0
    uat_total = 0
    
    if 'Stage QA recurrence' in df.columns:
        qa_rec = pd.to_numeric(df['Stage QA recurrence'], errors='coerce').fillna(0)
        qa_total = int((qa_rec - 1).clip(lower=0).sum())
    
    if 'Stage UAT recurrence' in df.columns:
        uat_rec = pd.to_numeric(df['Stage UAT recurrence'], errors='coerce').fillna(0)
        uat_total = int((uat_rec - 1).clip(lower=0).sum())
    
    # CFR = (QA_recurrence + UAT_recurrence) / Deployments
    cfr = (total_failure_signals / total_deployments) * 100 if total_deployments > 0 else 0
    
    return {
        'total_deployments': total_deployments,
        'total_failure_signals': int(total_failure_signals),
        'qa_recurrence_total': qa_total,
        'uat_recurrence_total': uat_total,
        'change_failure_rate': round(cfr, 1),
        'tickets_with_failures': int(tickets_with_failures),
    }


def get_tickets_with_failures(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get all tickets that have failure signals (QA/UAT recurrence).
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame of tickets with failures
    """
    df_temp = df.copy()
    df_temp['_failure_signals'] = df_temp.apply(calculate_failure_signals, axis=1)
    
    failed = df_temp[df_temp['_failure_signals'] > 0].copy()
    failed = failed.rename(columns={'_failure_signals': 'Failure_Signals'})
    
    return failed.sort_values('Failure_Signals', ascending=False)


def change_failure_rate_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Change Failure Rate grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' column and stage columns
        
    Returns:
        DataFrame with CFR stats per type
    """
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        cfr_stats = calculate_change_failure_rate(type_df)
        
        if cfr_stats['total_deployments'] > 0:
            results.append({
                'Type': ticket_type,
                'Deployments': cfr_stats['total_deployments'],
                'Failure Signals': cfr_stats['total_failure_signals'],
                'CFR (%)': cfr_stats['change_failure_rate'],
                'Tickets w/ Failures': cfr_stats['tickets_with_failures'],
            })
    
    return pd.DataFrame(results).sort_values('CFR (%)', ascending=True) if results else pd.DataFrame()


def get_change_failure_rate_rating(cfr_pct: float) -> Tuple[str, str]:
    """
    Get DORA performance rating based on Change Failure Rate.
    
    Benchmarks:
    - Elite: 0-15%
    - Medium: 16-30%
    - Low: > 30%
    
    Args:
        cfr_pct: Change failure rate percentage (0-100)
        
    Returns:
        Tuple of (rating, color)
    """
    if cfr_pct <= 15:
        return 'Elite', '#22c55e'  # Green
    elif cfr_pct <= 30:
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# MEAN TIME TO RESTORE (MTTR)
# =============================================================================
# What: How fast engineering fixes production issues
# From Jira: MTTR = Resolved_start - On_Production_start
# Why: Measures resilience and incident response capability
#
# Benchmarks:
#   - Elite: < 1 hour
#   - High: < 1 day
#   - Medium: 1-7 days
#   - Low: > 1 week

def calculate_mttr(df: pd.DataFrame) -> pd.Series:
    """
    Calculate Mean Time to Restore for each ticket.
    
    MTTR = Stage Resolved start - Stage On Production start
    
    This measures how fast issues are fixed after reaching production.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Series with MTTR in hours (None if not calculable)
    """
    
    def get_mttr(row):
        # Get On Production start date
        on_prod_start = parse_date(row.get('Stage On Production start'))
        if not on_prod_start:
            return None
        
        # Get Resolved start date
        resolved_start = parse_date(row.get('Stage Resolved start'))
        
        # Fallback to Done or Closed if Resolved not available
        if not resolved_start:
            resolved_start = parse_date(row.get('Stage Done start'))
        if not resolved_start:
            resolved_start = parse_date(row.get('Stage Closed start'))
        
        if not resolved_start:
            return None
        
        # Calculate MTTR in hours
        if resolved_start >= on_prod_start:
            return (resolved_start - on_prod_start).total_seconds() / 3600  # Convert to hours
        
        return None
    
    return df.apply(get_mttr, axis=1)


def mttr_stats(df: pd.DataFrame) -> dict:
    """
    Calculate Mean Time to Restore statistics.
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        Dictionary with MTTR statistics
    """
    if 'MTTR_Hours' not in df.columns:
        df = df.copy()
        df['MTTR_Hours'] = calculate_mttr(df)
    
    valid = pd.to_numeric(df['MTTR_Hours'], errors='coerce').dropna()
    
    if len(valid) == 0:
        return {
            'count': 0,
            'mean_hours': 0,
            'median_hours': 0,
            'mean_days': 0,
            'median_days': 0,
            'p90_hours': 0,
            'min_hours': 0,
            'max_hours': 0,
        }
    
    return {
        'count': len(valid),
        'mean_hours': round(valid.mean(), 1),
        'median_hours': round(valid.median(), 1),
        'mean_days': round(valid.mean() / 24, 1),
        'median_days': round(valid.median() / 24, 1),
        'p90_hours': round(valid.quantile(0.90), 1),
        'min_hours': round(valid.min(), 1),
        'max_hours': round(valid.max(), 1),
    }


def mttr_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate MTTR statistics grouped by ticket Type.
    
    Args:
        df: DataFrame with 'Type' and stage columns
        
    Returns:
        DataFrame with MTTR stats per type
    """
    if 'MTTR_Hours' not in df.columns:
        df = df.copy()
        df['MTTR_Hours'] = calculate_mttr(df)
    
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    results = []
    for ticket_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == ticket_type]
        valid = pd.to_numeric(type_df['MTTR_Hours'], errors='coerce').dropna()
        
        if len(valid) > 0:
            results.append({
                'Type': ticket_type,
                'Count': len(valid),
                'Median (hours)': round(valid.median(), 1),
                'Mean (hours)': round(valid.mean(), 1),
                'Median (days)': round(valid.median() / 24, 1),
            })
    
    return pd.DataFrame(results).sort_values('Median (hours)', ascending=True) if results else pd.DataFrame()


def mttr_by_priority(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate MTTR statistics grouped by Priority.
    
    Args:
        df: DataFrame with 'Level' (priority) and stage columns
        
    Returns:
        DataFrame with MTTR stats per priority
    """
    if 'MTTR_Hours' not in df.columns:
        df = df.copy()
        df['MTTR_Hours'] = calculate_mttr(df)
    
    priority_col = 'Level'
    if priority_col not in df.columns:
        return pd.DataFrame()
    
    results = []
    for priority in df[priority_col].dropna().unique():
        priority_df = df[df[priority_col] == priority]
        valid = pd.to_numeric(priority_df['MTTR_Hours'], errors='coerce').dropna()
        
        if len(valid) > 0:
            results.append({
                'Priority': priority,
                'Count': len(valid),
                'Median (hours)': round(valid.median(), 1),
                'Mean (hours)': round(valid.mean(), 1),
                'P90 (hours)': round(valid.quantile(0.90), 1),
            })
    
    return pd.DataFrame(results).sort_values('Median (hours)', ascending=True) if results else pd.DataFrame()


def get_tickets_with_mttr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get all tickets that have MTTR data (went to production and were resolved).
    
    Args:
        df: DataFrame with stage columns
        
    Returns:
        DataFrame of tickets with MTTR values
    """
    df_temp = df.copy()
    df_temp['MTTR_Hours'] = calculate_mttr(df_temp)
    
    with_mttr = df_temp[df_temp['MTTR_Hours'].notna()].copy()
    return with_mttr.sort_values('MTTR_Hours', ascending=False)


def get_mttr_rating(median_hours: float) -> Tuple[str, str]:
    """
    Get DORA performance rating based on Mean Time to Restore.
    
    Benchmarks:
    - Elite: < 1 hour
    - High: < 1 day (24 hours)
    - Medium: 1-7 days (24-168 hours)
    - Low: > 1 week (> 168 hours)
    
    Args:
        median_hours: Median MTTR in hours
        
    Returns:
        Tuple of (rating, color)
    """
    if median_hours < 1:
        return 'Elite', '#22c55e'  # Green
    elif median_hours < 24:
        return 'High', '#3b82f6'   # Blue
    elif median_hours < 168:  # 7 days * 24 hours
        return 'Medium', '#f59e0b' # Orange
    else:
        return 'Low', '#ef4444'    # Red


# =============================================================================
# DORA SUMMARY & DASHBOARD
# =============================================================================

def calculate_dora_summary(df: pd.DataFrame, sprint_duration_days: int = 14) -> dict:
    """
    Calculate a complete DORA metrics summary.
    
    Args:
        df: DataFrame with stage columns
        sprint_duration_days: Number of days in the sprint
        
    Returns:
        Dictionary with all DORA metrics and ratings
    """
    # Deployment Frequency
    df_stats = calculate_deployment_frequency(df, sprint_duration_days)
    df_rating, df_color = get_deployment_frequency_rating(df_stats['deployments_per_week'])
    
    # Lead Time for Changes
    ltc_stats = lead_time_for_changes_stats(df)
    ltc_rating, ltc_color = get_lead_time_for_changes_rating(ltc_stats['median'])
    
    # Change Failure Rate
    cfr_stats = calculate_change_failure_rate(df)
    cfr_rating, cfr_color = get_change_failure_rate_rating(cfr_stats['change_failure_rate'])
    
    # Mean Time to Restore
    mttr_data = mttr_stats(df)
    mttr_rating, mttr_color = get_mttr_rating(mttr_data['median_hours'])
    
    return {
        'deployment_frequency': {
            'stats': df_stats,
            'rating': df_rating,
            'color': df_color,
        },
        'lead_time_for_changes': {
            'stats': ltc_stats,
            'rating': ltc_rating,
            'color': ltc_color,
        },
        'change_failure_rate': {
            'stats': cfr_stats,
            'rating': cfr_rating,
            'color': cfr_color,
        },
        'mttr': {
            'stats': mttr_data,
            'rating': mttr_rating,
            'color': mttr_color,
        },
    }


def get_overall_dora_rating(summary: dict) -> Tuple[str, str]:
    """
    Calculate overall DORA performance rating.
    
    The overall rating is based on the distribution of individual metric ratings:
    - Elite: All 4 metrics are Elite or High
    - High: At least 3 metrics are High or better
    - Medium: At least 2 metrics are Medium or better
    - Low: Otherwise
    
    Args:
        summary: Dictionary from calculate_dora_summary()
        
    Returns:
        Tuple of (rating, color)
    """
    rating_scores = {'Elite': 4, 'High': 3, 'Medium': 2, 'Low': 1}
    
    ratings = [
        summary['deployment_frequency']['rating'],
        summary['lead_time_for_changes']['rating'],
        summary['change_failure_rate']['rating'],
        summary['mttr']['rating'],
    ]
    
    scores = [rating_scores.get(r, 1) for r in ratings]
    avg_score = sum(scores) / len(scores)
    
    if avg_score >= 3.5:
        return 'Elite', '#22c55e'
    elif avg_score >= 2.5:
        return 'High', '#3b82f6'
    elif avg_score >= 1.5:
        return 'Medium', '#f59e0b'
    else:
        return 'Low', '#ef4444'


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_hours_human(hours: float) -> str:
    """
    Format hours into human-readable time string.
    
    Args:
        hours: Time in hours
        
    Returns:
        Formatted string (e.g., "2h", "1d 4h", "1w 2d")
    """
    if pd.isna(hours) or hours <= 0:
        return "—"
    
    if hours < 1:
        return f"{int(hours * 60)}m"
    elif hours < 24:
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    elif hours < 168:  # Less than 1 week
        days = hours / 24
        d = int(days)
        h = int((days - d) * 24)
        return f"{d}d {h}h" if h > 0 else f"{d}d"
    else:
        weeks = hours / 168
        w = int(weeks)
        d = int((weeks - w) * 7)
        return f"{w}w {d}d" if d > 0 else f"{w}w"


def format_frequency_human(per_week: float) -> str:
    """
    Format deployment frequency into human-readable string.
    
    Args:
        per_week: Deployments per week
        
    Returns:
        Formatted string (e.g., "Daily", "Weekly", "Monthly")
    """
    if per_week >= 7:
        return f"{per_week/7:.1f}/day (Elite)"
    elif per_week >= 1:
        return f"{per_week:.1f}/week (High)"
    elif per_week >= 0.25:
        return f"{per_week*4:.1f}/month (Medium)"
    else:
        return f"<{0.25*4:.1f}/month (Low)"


# DORA Benchmarks reference (matching your specifications)
DORA_BENCHMARKS = {
    'deployment_frequency': {
        'Elite': 'On-demand / daily',
        'High': 'Weekly',
        'Medium': 'Monthly',
        'Low': 'Quarterly',
    },
    'lead_time_for_changes': {
        'Elite': '< 1 day',
        'High': '1-7 days',
        'Medium': '1-4 weeks',
        'Low': '> 1 month',
    },
    'change_failure_rate': {
        'Elite': '0-15%',
        'Medium': '16-30%',
        'Low': '> 30%',
    },
    'mttr': {
        'Elite': '< 1 hour',
        'High': '< 1 day',
        'Medium': '1-7 days',
        'Low': '> 1 week',
    },
}

