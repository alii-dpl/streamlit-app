"""
DORA Metrics Calculations
"""
import pandas as pd
import numpy as np


def load_jira_csv(file, debug: bool = True) -> tuple:
    """
    Load CSV and immediately filter out obsolete/duplicate tickets.
    Returns: (filtered_df, total_raw_count, obsolete_count)
    """
    file.seek(0)
    df = pd.read_csv(file, sep=';', encoding='utf-8', quotechar='"')
    
    # Strip quotes from column names
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # Strip quotes from string values (preserve NaN)
    for col in df.columns:
        if df[col].dtype == 'object':
            mask = df[col].notna()
            df.loc[mask, col] = df.loc[mask, col].astype(str).str.strip().str.strip('"')
            df[col] = df[col].replace('', np.nan)
    
    total_raw = len(df)
    
    if debug:
        print("\n=== DEBUG: load_jira_csv (BEFORE filtering) ===")
        print(f"  Total rows: {total_raw}")
        for col in ['Stage UAT start', 'Stage Done start']:
            if col in df.columns:
                non_null = df[col].notna().sum()
                print(f"  {col}: {non_null} non-null values")
    
    # FIRST STEP: Remove obsolete and duplicate tickets
    obsolete_cols = ['Stage Obsolete days', 'Stage Duplicate days']
    keep_mask = pd.Series([True] * len(df), index=df.index)
    
    if debug:
        print(f"  Columns in CSV: {list(df.columns[:10])}...")  # First 10 columns
    
    for col in obsolete_cols:
        if col in df.columns:
            col_vals = pd.to_numeric(df[col], errors='coerce').fillna(0)
            rows_to_remove = (col_vals > 0).sum()
            if debug:
                print(f"  {col}: FOUND - {rows_to_remove} rows have value > 0")
                if rows_to_remove > 0:
                    print(f"    Sample values being removed: {col_vals[col_vals > 0].head(3).tolist()}")
            keep_mask = keep_mask & (col_vals == 0)
        else:
            if debug:
                print(f"  {col}: NOT FOUND in columns")
    
    df = df[keep_mask].copy()
    obsolete_count = total_raw - len(df)
    
    if debug:
        print(f"  ACTUALLY REMOVED: {obsolete_count} rows")
    
    if debug:
        print(f"\n=== DEBUG: load_jira_csv (AFTER filtering) ===")
        print(f"  Remaining rows: {len(df)}")
        for col in ['Stage UAT start', 'Stage Done start']:
            if col in df.columns:
                non_null = df[col].notna().sum()
                print(f"  {col}: {non_null} non-null values")
        print("=== END DEBUG ===\n")
    
    return df, total_raw, obsolete_count


def get_stage_days_columns(df: pd.DataFrame) -> list:
    return [col for col in df.columns if col.startswith('Stage ') and col.endswith(' days')]


def get_stage_start_columns(df: pd.DataFrame) -> list:
    return [col for col in df.columns if col.startswith('Stage ') and col.endswith(' start')]


def get_stage_recurrence_columns(df: pd.DataFrame) -> list:
    return [col for col in df.columns if col.startswith('Stage ') and col.endswith(' recurrence')]


# =============================================================================
# LEAD TIME
# =============================================================================

def calculate_lead_time(df: pd.DataFrame) -> pd.Series:
    """Lead Time = Days from first stage start to last stage start"""
    start_cols = get_stage_start_columns(df)
    
    def row_lead_time(row):
        dates = []
        for col in start_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip() != '':
                try:
                    dates.append(pd.to_datetime(str(val).strip()))
                except:
                    pass
        if len(dates) >= 2:
            return (max(dates) - min(dates)).days
        return None
    
    return df.apply(row_lead_time, axis=1)


def lead_time_average(df: pd.DataFrame) -> float:
    valid = pd.to_numeric(df['Lead_Time'], errors='coerce').dropna()
    return float(valid.mean()) if len(valid) > 0 else 0.0


def lead_time_median(df: pd.DataFrame) -> float:
    valid = pd.to_numeric(df['Lead_Time'], errors='coerce').dropna()
    return float(valid.median()) if len(valid) > 0 else 0.0


def lead_time_percentile_90(df: pd.DataFrame) -> float:
    valid = pd.to_numeric(df['Lead_Time'], errors='coerce').dropna()
    return float(valid.quantile(0.9)) if len(valid) > 0 else 0.0


# =============================================================================
# CYCLE TIME
# =============================================================================

def calculate_cycle_time(df: pd.DataFrame) -> pd.Series:
    """Cycle Time = Sum of all stage days"""
    days_cols = get_stage_days_columns(df)
    
    def row_cycle_time(row):
        total = 0
        for col in days_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip() != '':
                try:
                    total += float(val)
                except:
                    pass
        return total if total > 0 else None
    
    return df.apply(row_cycle_time, axis=1)


def cycle_time_average(df: pd.DataFrame) -> float:
    valid = pd.to_numeric(df['Cycle_Time'], errors='coerce').dropna()
    return float(valid.mean()) if len(valid) > 0 else 0.0


def cycle_time_median(df: pd.DataFrame) -> float:
    valid = pd.to_numeric(df['Cycle_Time'], errors='coerce').dropna()
    return float(valid.median()) if len(valid) > 0 else 0.0


def cycle_time_percentile_90(df: pd.DataFrame) -> float:
    valid = pd.to_numeric(df['Cycle_Time'], errors='coerce').dropna()
    return float(valid.quantile(0.9)) if len(valid) > 0 else 0.0


# =============================================================================
# DONE DATE (UAT or Done = completed)
# =============================================================================

def is_valid_date_value(val) -> bool:
    """Check if value is a valid non-blank date string"""
    if pd.isna(val):
        return False
    s = str(val).strip()
    if s == '' or s.lower() == 'nan' or s.lower() == 'nat':
        return False
    return True


def calculate_done_date(df: pd.DataFrame, debug: bool = True) -> pd.Series:
    """
    Done = ticket where 'Stage UAT start' OR 'Stage Done start' is NOT blank/empty
    Returns the earliest of the two dates if both exist
    """
    def parse_date(val):
        if not is_valid_date_value(val):
            return pd.NaT
        try:
            return pd.to_datetime(str(val).strip())
        except:
            return pd.NaT
    
    # Debug: Check what's in the columns
    if debug:
        print("\n=== DEBUG: calculate_done_date ===")
        for col in ['Stage UAT start', 'Stage Done start']:
            if col in df.columns:
                valid_count = df[col].apply(is_valid_date_value).sum()
                print(f"  {col}: {valid_count} valid (non-blank) values")
                # Show sample values
                valid_samples = df[df[col].apply(is_valid_date_value)][col].head(3).tolist()
                print(f"    Sample values: {valid_samples}")
            else:
                print(f"  {col}: COLUMN NOT FOUND")
    
    def get_done_date(row):
        dates = []
        for col in ['Stage UAT start', 'Stage Done start']:
            if col in df.columns:
                dt = parse_date(row.get(col))
                if pd.notna(dt):
                    dates.append(dt)
        return min(dates) if dates else pd.NaT
    
    result = df.apply(get_done_date, axis=1)
    
    if debug:
        completed = result.notna().sum()
        incomplete = result.isna().sum()
        print(f"  RESULT: {completed} completed, {incomplete} incomplete")
        print("=== END DEBUG ===\n")
    
    return result


# =============================================================================
# DEPLOYMENT FREQUENCY
# =============================================================================

def deployment_frequency(df: pd.DataFrame) -> float:
    """Deployment Frequency = Completed issues per day"""
    valid = df['Done_Date'].dropna()
    if len(valid) < 2:
        return 0.0
    date_range = (valid.max() - valid.min()).days
    return float(len(valid) / max(date_range, 1))


# =============================================================================
# CHANGE FAILURE RATE
# =============================================================================

def change_failure_rate(df: pd.DataFrame) -> float:
    """Change Failure Rate = (Bugs / Total Issues) × 100"""
    if 'Type' not in df.columns or len(df) == 0:
        return 0.0
    type_lower = df['Type'].astype(str).str.lower()
    bug_count = type_lower.str.contains('bug|defect', na=False, regex=True).sum()
    return float(bug_count / len(df) * 100)


def bug_count(df: pd.DataFrame) -> int:
    if 'Type' not in df.columns:
        return 0
    type_lower = df['Type'].astype(str).str.lower()
    return int(type_lower.str.contains('bug|defect', na=False, regex=True).sum())


# =============================================================================
# MEAN TIME TO RECOVERY
# =============================================================================

def mean_time_to_recovery(df: pd.DataFrame) -> float:
    """MTTR = Average lead time for bugs"""
    if 'Type' not in df.columns:
        return 0.0
    type_lower = df['Type'].astype(str).str.lower()
    bug_mask = type_lower.str.contains('bug|defect', na=False, regex=True)
    bug_lead_times = pd.to_numeric(df.loc[bug_mask, 'Lead_Time'], errors='coerce').dropna()
    return float(bug_lead_times.mean()) if len(bug_lead_times) > 0 else 0.0


# =============================================================================
# BACKTRACKS
# =============================================================================

def calculate_backtracks(df: pd.DataFrame) -> pd.Series:
    """Backtrack = Stage entered more than once (recurrence > 1)"""
    recurrence_cols = get_stage_recurrence_columns(df)
    
    def row_backtracks(row):
        count = 0
        for col in recurrence_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip() != '':
                try:
                    if int(float(val)) > 1:
                        count += 1
                except:
                    pass
        return count
    
    return df.apply(row_backtracks, axis=1)


def total_backtracks(df: pd.DataFrame) -> int:
    return int(pd.to_numeric(df['Backtracks'], errors='coerce').fillna(0).sum())


def backtrack_rate(df: pd.DataFrame) -> float:
    if len(df) == 0:
        return 0.0
    issues_with_backtracks = (pd.to_numeric(df['Backtracks'], errors='coerce').fillna(0) > 0).sum()
    return float(issues_with_backtracks / len(df) * 100)


def backtracks_by_stage(df: pd.DataFrame) -> pd.DataFrame:
    recurrence_cols = get_stage_recurrence_columns(df)
    result = []
    for col in recurrence_cols:
        stage_name = col.replace('Stage ', '').replace(' recurrence', '')
        vals = pd.to_numeric(df[col], errors='coerce')
        count = (vals > 1).sum()
        if count > 0:
            result.append({'Stage': stage_name, 'Backtracks': count})
    return pd.DataFrame(result).sort_values('Backtracks', ascending=True) if result else pd.DataFrame()


# =============================================================================
# THROUGHPUT
# =============================================================================

def throughput_total(df: pd.DataFrame) -> int:
    return len(df)


def throughput_completed(df: pd.DataFrame) -> int:
    return int(df['Done_Date'].notna().sum())


def weekly_throughput(df: pd.DataFrame) -> pd.DataFrame:
    valid = df['Done_Date'].dropna()
    if len(valid) == 0:
        return pd.DataFrame(columns=['Week', 'Count'])
    weeks = valid.dt.isocalendar().week
    counts = weeks.value_counts().sort_index().reset_index()
    counts.columns = ['Week', 'Count']
    return counts


def monthly_throughput(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['_done_month'] = df['Done_Date'].dt.to_period('M').astype(str)
    valid = df[df['_done_month'].notna() & (df['_done_month'] != 'NaT')]
    if len(valid) == 0 or 'Type' not in valid.columns:
        return pd.DataFrame()
    return valid.groupby(['_done_month', 'Type']).size().unstack(fill_value=0)


# =============================================================================
# CYCLE TIME BY STAGE
# =============================================================================

def cycle_time_by_stage_and_type(df: pd.DataFrame) -> pd.DataFrame:
    if 'Type' not in df.columns:
        return pd.DataFrame()
    
    days_cols = get_stage_days_columns(df)
    result = []
    
    for issue_type in df['Type'].dropna().unique():
        type_df = df[df['Type'] == issue_type]
        row = {'Type': issue_type}
        for col in days_cols:
            stage_name = col.replace('Stage ', '').replace(' days', '')
            values = pd.to_numeric(type_df[col], errors='coerce').dropna()
            row[stage_name] = float(values.median()) if len(values) > 0 else 0
        result.append(row)
    
    return pd.DataFrame(result)


# =============================================================================
# INVESTMENT ALLOCATION
# =============================================================================

def issues_by_type(df: pd.DataFrame) -> pd.Series:
    if 'Type' not in df.columns:
        return pd.Series()
    return df['Type'].value_counts()


def issues_by_component(df: pd.DataFrame) -> pd.Series:
    if 'Components' not in df.columns:
        return pd.Series()
    return df['Components'].value_counts().head(10)


def issues_by_label(df: pd.DataFrame) -> pd.Series:
    if 'Labels' not in df.columns:
        return pd.Series()
    return df['Labels'].value_counts().head(10)


def issues_by_assignee(df: pd.DataFrame) -> pd.Series:
    if 'AssigneeName' not in df.columns:
        return pd.Series()
    return df['AssigneeName'].value_counts().head(10)


# =============================================================================
# STORY POINTS
# =============================================================================

def get_story_points_column(df: pd.DataFrame) -> str:
    """Find story points column"""
    candidates = ['StoryPoints', 'Story Points', 'Story points', 'storypoints']
    for col in candidates:
        if col in df.columns:
            return col
    for col in df.columns:
        if 'story' in col.lower() and 'point' in col.lower():
            return col
    return None


def has_story_points(df: pd.DataFrame) -> bool:
    return get_story_points_column(df) is not None


def story_points_total(df: pd.DataFrame) -> float:
    """Total Story Points = SUM(StoryPoints)"""
    col = get_story_points_column(df)
    if not col:
        return 0.0
    return float(pd.to_numeric(df[col], errors='coerce').fillna(0).sum())


def story_points_completed(df: pd.DataFrame) -> float:
    """Completed Story Points = SUM(StoryPoints) where Done_Date is not null"""
    col = get_story_points_column(df)
    if not col:
        return 0.0
    completed = df[df['Done_Date'].notna()]
    return float(pd.to_numeric(completed[col], errors='coerce').fillna(0).sum())


def story_points_average(df: pd.DataFrame) -> float:
    """Average Story Points per Issue"""
    col = get_story_points_column(df)
    if not col:
        return 0.0
    valid = pd.to_numeric(df[col], errors='coerce').dropna()
    valid = valid[valid > 0]
    return float(valid.mean()) if len(valid) > 0 else 0.0


def story_points_by_type(df: pd.DataFrame) -> pd.Series:
    """Story Points grouped by issue Type"""
    col = get_story_points_column(df)
    if not col or 'Type' not in df.columns:
        return pd.Series()
    df = df.copy()
    df['_sp'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df.groupby('Type')['_sp'].sum().sort_values(ascending=False)


def story_points_by_assignee(df: pd.DataFrame) -> pd.Series:
    """Story Points grouped by Assignee"""
    col = get_story_points_column(df)
    if not col or 'AssigneeName' not in df.columns:
        return pd.Series()
    df = df.copy()
    df['_sp'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df.groupby('AssigneeName')['_sp'].sum().sort_values(ascending=False).head(10)


def story_points_by_component(df: pd.DataFrame) -> pd.Series:
    """Story Points grouped by Component"""
    col = get_story_points_column(df)
    if not col or 'Components' not in df.columns:
        return pd.Series()
    df = df.copy()
    df['_sp'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df.groupby('Components')['_sp'].sum().sort_values(ascending=False).head(10)


def velocity_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Weekly velocity = Story Points completed per week"""
    col = get_story_points_column(df)
    if not col:
        return pd.DataFrame(columns=['Week', 'StoryPoints'])
    df = df.copy()
    df['_sp'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    valid = df[df['Done_Date'].notna()]
    if len(valid) == 0:
        return pd.DataFrame(columns=['Week', 'StoryPoints'])
    valid = valid.copy()
    valid['_week'] = valid['Done_Date'].dt.isocalendar().week
    result = valid.groupby('_week')['_sp'].sum().reset_index()
    result.columns = ['Week', 'StoryPoints']
    return result


def lead_time_per_story_point(df: pd.DataFrame) -> float:
    """Lead Time efficiency = Average Lead Time per Story Point"""
    col = get_story_points_column(df)
    if not col:
        return 0.0
    df = df.copy()
    df['_sp'] = pd.to_numeric(df[col], errors='coerce')
    df['_lt'] = pd.to_numeric(df['Lead_Time'], errors='coerce')
    valid = df[(df['_sp'] > 0) & (df['_lt'] > 0)]
    if len(valid) == 0:
        return 0.0
    return float((valid['_lt'] / valid['_sp']).mean())


# =============================================================================
# DORA RATING
# =============================================================================

DORA_THRESHOLDS = {
    'lead_time': [(1, 'Elite'), (7, 'High'), (30, 'Medium'), (float('inf'), 'Low')],
    'deploy_freq': [(1, 'Elite'), (0.14, 'High'), (0.033, 'Medium'), (0, 'Low')],
    'change_failure_rate': [(15, 'Elite'), (30, 'High'), (45, 'Medium'), (float('inf'), 'Low')],
    'mttr': [(0.04, 'Elite'), (1, 'High'), (7, 'Medium'), (float('inf'), 'Low')]
}

RATING_COLORS = {
    'Elite': '#22c55e',
    'High': '#3b82f6',
    'Medium': '#f59e0b',
    'Low': '#ef4444'
}


def get_dora_rating(metric: str, value: float) -> tuple:
    if metric not in DORA_THRESHOLDS:
        return 'N/A', '#808080'
    
    for threshold, rating in DORA_THRESHOLDS[metric]:
        if metric in ['lead_time', 'change_failure_rate', 'mttr']:
            if value <= threshold:
                return rating, RATING_COLORS[rating]
        else:
            if value >= threshold:
                return rating, RATING_COLORS[rating]
    
    return 'Low', RATING_COLORS['Low']
