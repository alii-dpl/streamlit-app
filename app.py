import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from io import StringIO

# Add jira-data-utils to path (inside streamlit_app folder)
jira_data_path = Path(__file__).parent / 'jira-data-utils'
sys.path.insert(0, str(jira_data_path))

from extractor import JiraExtractor
from jira_types import JiraExtractorConfig, Auth, ConnectionConfig

# Import metrics
from metrics import (
    calculate_cycle_time,
    cycle_time_stats,
    cycle_time_by_type,
    identify_outliers,
    get_cycle_time_rating,
    get_stage_time_summary,
    get_stage_time_chart_data,
    get_stage_bottlenecks,
    STAGE_CATEGORIES,
    calculate_lead_time,
    lead_time_stats,
    lead_time_by_type,
    calculate_wait_time,
    get_lead_time_rating,
    calculate_flow_efficiency,
    calculate_active_time,
    calculate_waiting_time,
    flow_efficiency_stats,
    flow_efficiency_by_type,
    waiting_time_breakdown,
    get_flow_efficiency_rating,
    calculate_dev_to_qa_ready_delay,
    calculate_qa_ready_to_qa_delay,
    calculate_total_handoff_delay,
    handoff_delay_stats,
    handoff_delay_by_type,
    handoff_breakdown,
    get_handoff_delay_rating,
    calculate_recurrence_count,
    calculate_bounce_count,
    recurrence_stats,
    recurrence_by_type,
    recurrence_breakdown,
    identify_high_recurrence_tickets,
    get_recurrence_rating,
    calculate_defect_escape,
    defect_escape_stats,
    defect_escape_by_type,
    defect_escape_breakdown,
    identify_escaped_defects,
    get_escape_rate_rating,
    calculate_estimation_accuracy,
    estimation_accuracy_stats,
    estimation_accuracy_by_type,
    identify_estimation_outliers,
    get_estimation_accuracy_rating,
    format_time_seconds,
)

# Import DORA metrics
from dora import (
    count_deployments,
    get_deployments,
    calculate_deployment_frequency,
    deployment_frequency_by_type,
    deployment_frequency_by_date,
    get_deployment_frequency_rating,
    calculate_lead_time_for_changes,
    lead_time_for_changes_stats,
    lead_time_for_changes_by_type,
    get_lead_time_for_changes_rating,
    calculate_change_failure_rate,
    change_failure_rate_by_type,
    get_tickets_with_failures,
    get_change_failure_rate_rating,
    calculate_mttr,
    mttr_stats,
    mttr_by_type,
    mttr_by_priority,
    get_tickets_with_mttr,
    get_mttr_rating,
    calculate_dora_summary,
    get_overall_dora_rating,
    format_hours_human,
    DORA_BENCHMARKS,
)

st.set_page_config(page_title="Sprint Story Points", page_icon="📊", layout="wide")

st.title("📊 Sprint Story Points Tracker")

# Jira configuration - credentials from secrets.toml, attributes defined here
def get_jira_config():
    """Get Jira configuration from secrets"""
    # Check if secrets are available
    if 'jira' not in st.secrets:
        st.error("❌ Jira credentials not found! Please configure `.streamlit/secrets.toml`")
        st.code("""
# .streamlit/secrets.toml
[jira]
domain = "https://your-domain.atlassian.net/"
username = "your-email@company.com"
password = "your-api-token"
        """, language="toml")
        st.stop()
    
    return {
        'domain': st.secrets['jira']['domain'],
        'username': st.secrets['jira']['username'],
        'password': st.secrets['jira']['password'],
        'attributes': {
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
    }


def fetch_jira_data(sprint_suffix: str) -> pd.DataFrame:
    """
    Fetch data from Jira for a given sprint
    
    Args:
        sprint_suffix: The sprint suffix (e.g., "2025-26")
        
    Returns:
        DataFrame with Jira data
    """
    # Get config from secrets
    jira_config = get_jira_config()
    
    full_sprint_name = f"iApts {sprint_suffix}"
    jql = f'Sprint = "{full_sprint_name}"'
    
    config = JiraExtractorConfig(
        connection=ConnectionConfig(
            url=jira_config['domain'],
            auth=Auth(
                username=jira_config['username'],
                password=jira_config['password']
            )
        ),
        custom_jql=jql,
        attributes=jira_config['attributes']
    )
    
    extractor = JiraExtractor(config)
    work_items = extractor.extract_all()
    csv_content = extractor.to_csv(work_items)
    
    # Parse CSV to DataFrame
    df = pd.read_csv(StringIO(csv_content), sep=';', encoding='utf-8', quotechar='"')
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    return df


def is_completed(stage_value):
    """Check if ticket is completed based on Stage column (UAT, Done, Released, Resolved, Closed, On Production, or Pending Unleash)"""
    if pd.notna(stage_value):
        stage_lower = str(stage_value).strip().lower()
        return stage_lower in ['uat', 'done', 'released', 'resolved', 'closed', 'on production', 'pending unleash']
    return False


def display_tickets_table(df, title_cols):
    """Display a dataframe as a table with clickable Jira links"""
    if len(df) == 0:
        st.info("No tickets to display")
        return
        
    available_cols = [c for c in title_cols if c in df.columns]
    display_df = df[available_cols].copy()
    
    column_config = {
        "Link": st.column_config.LinkColumn("Link", display_text="Open in Jira"),
        "ID": st.column_config.TextColumn("ID"),
        "Name": st.column_config.TextColumn("Name", width="large"),
        "Type": st.column_config.TextColumn("Type"),
        "StoryPoints": st.column_config.NumberColumn("SP"),
        "Stage": st.column_config.TextColumn("Stage"),
        "AssigneeName": st.column_config.TextColumn("Assignee"),
    }
    
    st.dataframe(
        display_df,
        column_config={k: v for k, v in column_config.items() if k in available_cols},
        hide_index=True,
        use_container_width=True
    )


def load_csv_file(file) -> pd.DataFrame:
    """Load and parse uploaded CSV file"""
    file.seek(0)
    df = pd.read_csv(file, sep=';', encoding='utf-8', quotechar='"')
    df.columns = df.columns.str.strip().str.replace('"', '')
    return df


def main():
    # Initialize session state for data
    if 'df_raw' not in st.session_state:
        st.session_state.df_raw = None
        st.session_state.current_sprint = None
        st.session_state.data_source = None
    
    # Data source selection
    st.subheader("📥 Data Source")
    
    tab_fetch, tab_upload = st.tabs(["🔄 Fetch from Jira", "📁 Upload CSV"])
    
    # Tab 1: Fetch from Jira
    with tab_fetch:
        col1, col2 = st.columns([2, 1])
        with col1:
            sprint_suffix = st.text_input(
                "Enter Sprint (e.g., 2025-26, 2026-01)",
                value="2025-26",
                placeholder="2025-26",
                help="Enter the sprint number. Will be converted to 'iApts 2025-26'"
            )
        
        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            fetch_button = st.button("🔄 Fetch Data", type="primary", use_container_width=True)
        
        # Show what query will be used
        if sprint_suffix:
            st.caption(f"📋 JQL Query: `Sprint = \"iApts {sprint_suffix}\"`")
        
        # Fetch data when button is clicked
        if fetch_button and sprint_suffix:
            with st.spinner(f"🔄 Fetching data for iApts {sprint_suffix}..."):
                try:
                    st.session_state.df_raw = fetch_jira_data(sprint_suffix)
                    st.session_state.current_sprint = sprint_suffix
                    st.session_state.data_source = 'jira'
                    st.success(f"✅ Loaded {len(st.session_state.df_raw)} tickets from iApts {sprint_suffix}")
                except Exception as e:
                    st.error(f"❌ Error fetching data: {str(e)}")
                    return
    
    # Tab 2: Upload CSV
    with tab_upload:
        uploaded_file = st.file_uploader(
            "Upload Jira CSV file",
            type=['csv'],
            help="Upload a CSV file exported from Jira or generated by the extractor"
        )
        
        if uploaded_file:
            try:
                st.session_state.df_raw = load_csv_file(uploaded_file)
                st.session_state.current_sprint = uploaded_file.name.replace('.csv', '')
                st.session_state.data_source = 'csv'
                st.success(f"✅ Loaded {len(st.session_state.df_raw)} tickets from {uploaded_file.name}")
            except Exception as e:
                st.error(f"❌ Error loading CSV: {str(e)}")
                return
    
    # If no data loaded yet
    if st.session_state.df_raw is None:
        st.info("👆 Enter a sprint number and click 'Fetch Data' to get started")
        return
    
    df_raw = st.session_state.df_raw
    total_raw = len(df_raw)
    
    st.divider()
    
    # =========================================================================
    # SIDEBAR FILTERS
    # =========================================================================
    with st.sidebar:
        st.header("🎛️ Filters")
        if st.session_state.get('data_source') == 'jira':
            st.caption(f"📡 Sprint: iApts {st.session_state.get('current_sprint', '')}")
        else:
            st.caption(f"📁 File: {st.session_state.get('current_sprint', '')}")
        
        st.divider()
        
        # Obsolete/Duplicate removal switches
        st.subheader("Remove Tickets")
        
        remove_obsolete = st.toggle("🗑️ Remove Obsolete", value=True, help="Remove tickets with 'Stage Obsolete days' > 0")
        remove_duplicate = st.toggle("📋 Remove Duplicate", value=True, help="Remove tickets with 'Stage Duplicate days' > 0")
        
        st.divider()
        
        # Story Points filter
        story_points_filters = {}
        if 'StoryPoints' in df_raw.columns:
            # Get unique story point values
            sp_values_raw = pd.to_numeric(df_raw['StoryPoints'], errors='coerce').dropna()
            # Convert to int, filter out NaN, and get unique values
            sp_values_set = set()
            for sp in sp_values_raw:
                if pd.notna(sp):
                    try:
                        sp_int = int(float(sp))  # Convert via float first to handle edge cases
                        sp_values_set.add(sp_int)
                    except (ValueError, OverflowError):
                        continue
            
            sp_values = sorted(list(sp_values_set))
            
            if len(sp_values) > 0:
                st.subheader("Filter by Story Points")
                st.caption("Toggle ON to include")
                
                # Create a toggle for each story point value with unique key
                # Ensure keys are unique by using a prefix and the value
                for idx, sp_value in enumerate(sp_values):
                    # Use index in key to ensure absolute uniqueness even if values somehow duplicate
                    unique_key = f"story_points_toggle_{idx}_{sp_value}"
                    story_points_filters[sp_value] = st.toggle(
                        f"{sp_value} SP", 
                        value=True, 
                        key=unique_key
                    )
        
        st.divider()
        
        # Get unique ticket types
        type_filters = {}
        if 'Type' in df_raw.columns:
            all_types = df_raw['Type'].dropna().unique().tolist()
            all_types = sorted(all_types)
            
            st.subheader("Filter by Type")
            st.caption("Toggle OFF to exclude")
            
            # Create a toggle for each type
            for ticket_type in all_types:
                type_filters[ticket_type] = st.toggle(
                    f"{ticket_type}", 
                    value=True, 
                    key=f"type_{ticket_type}"
                )
        
        st.divider()
        
        # Metric visibility toggles
        st.subheader("📊 Show Metrics")
        st.caption("Toggle to show/hide sections")
        
        show_story_points = st.toggle("🎯 Story Points", value=True, key="show_story_points")
        show_dora = st.toggle("🚀 DORA Metrics [Beta]", value=True, key="show_dora")
        show_stage_time = st.toggle("📊 Stage Time Analysis", value=True, key="show_stage_time")
        show_cycle_time = st.toggle("⏱️ Cycle Time", value=True, key="show_cycle_time")
        show_lead_time = st.toggle("📏 Lead Time", value=True, key="show_lead_time")
        show_handoff_delay = st.toggle("🤝 Handoff Delay", value=True, key="show_handoff_delay")
        show_quality = st.toggle("🔄 Quality & Stability", value=True, key="show_quality")
        show_estimation = st.toggle("🎯 Estimation Accuracy", value=True, key="show_estimation")
        show_standout = st.toggle("🔍 Standout Tickets", value=True, key="show_standout")
    
    # =========================================================================
    # Apply filters to create df_active and df_removed
    # =========================================================================
    
    # Start with all tickets
    df_working = df_raw.copy()
    
    # Track removed tickets
    removed_mask = pd.Series([False] * len(df_working), index=df_working.index)
    
    # Apply Obsolete filter
    obsolete_count = 0
    if remove_obsolete and 'Stage Obsolete days' in df_working.columns:
        obsolete_vals = pd.to_numeric(df_working['Stage Obsolete days'], errors='coerce').fillna(0)
        obsolete_mask = obsolete_vals > 0
        obsolete_count = obsolete_mask.sum()
        removed_mask = removed_mask | obsolete_mask
    
    # Apply Duplicate filter
    duplicate_count = 0
    if remove_duplicate and 'Stage Duplicate days' in df_working.columns:
        duplicate_vals = pd.to_numeric(df_working['Stage Duplicate days'], errors='coerce').fillna(0)
        duplicate_mask = duplicate_vals > 0
        duplicate_count = duplicate_mask.sum()
        removed_mask = removed_mask | duplicate_mask
    
    # Create removed dataframe (for display only)
    df_removed = df_working[removed_mask].copy().reset_index(drop=True)
    
    # Create active dataframe (after obsolete/duplicate removal)
    df_active = df_working[~removed_mask].copy().reset_index(drop=True)
    
    # Apply Type filters
    type_removed_count = 0
    if 'Type' in df_active.columns and type_filters:
        selected_types = [t for t, selected in type_filters.items() if selected]
        excluded_types = [t for t, selected in type_filters.items() if not selected]
        
        if excluded_types:
            type_mask = df_active['Type'].isin(selected_types)
            type_removed_count = (~type_mask).sum()
            df_active = df_active[type_mask].copy().reset_index(drop=True)
    
    # Apply Story Points filters
    sp_removed_count = 0
    if 'StoryPoints' in df_active.columns and story_points_filters:
        selected_sp_values = [sp for sp, selected in story_points_filters.items() if selected]
        excluded_sp_values = [sp for sp, selected in story_points_filters.items() if not selected]
        
        # Only apply filter if some story points are excluded AND at least one is selected
        if excluded_sp_values and selected_sp_values:
            # Convert StoryPoints to numeric and filter
            df_active['_sp_numeric'] = pd.to_numeric(df_active['StoryPoints'], errors='coerce')
            sp_mask = df_active['_sp_numeric'].isin(selected_sp_values)
            sp_removed_count = (~sp_mask).sum()
            df_active = df_active[sp_mask].copy().reset_index(drop=True)
            # Remove temporary column
            df_active = df_active.drop(columns=['_sp_numeric'], errors='ignore')
    
    removed_count = len(df_removed)
    
    # =========================================================================
    # Show filtering summary
    # =========================================================================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Loaded", total_raw)
    with col2:
        st.metric("Obsolete Removed", obsolete_count, delta=f"-{obsolete_count}" if obsolete_count > 0 else None, delta_color="inverse")
    with col3:
        st.metric("Duplicate Removed", duplicate_count, delta=f"-{duplicate_count}" if duplicate_count > 0 else None, delta_color="inverse")
    with col4:
        st.metric("Active Tickets", len(df_active))
    
    if sp_removed_count > 0 and story_points_filters:
        selected_sp = [sp for sp, selected in story_points_filters.items() if selected]
        if selected_sp:
            st.info(f"🎯 **{sp_removed_count}** tickets filtered out by Story Points selection (showing: {', '.join(map(str, selected_sp))} SP)")
    
    if type_removed_count > 0:
        st.info(f"📋 **{type_removed_count}** tickets filtered out by Type selection")
    
    # Show removed tickets (obsolete/duplicate only)
    if removed_count > 0:
        with st.expander(f"🗑️ Click to view {removed_count} removed tickets (Obsolete/Duplicate)"):
            display_tickets_table(df_removed, ['ID', 'Link', 'Name', 'Type'])
    
    st.divider()
    
    # =========================================================================
    # ALL CALCULATIONS USE df_active ONLY
    # =========================================================================
    
    if len(df_active) == 0:
        st.warning("⚠️ No tickets remaining after filters. Adjust your filters.")
        return
    
    # Check for StoryPoints column
    if 'StoryPoints' not in df_active.columns:
        st.error("❌ No 'StoryPoints' column found in the data")
        return
    
    # Convert story points to numeric
    df_active['_sp'] = pd.to_numeric(df_active['StoryPoints'], errors='coerce').fillna(0)
    
    # Determine completed tickets based on Stage column
    df_active['_completed'] = df_active['Stage'].apply(is_completed)
    
    # Split into completed and remaining
    df_completed = df_active[df_active['_completed']].copy()
    df_remaining = df_active[~df_active['_completed']].copy()
    
    # Calculate story points
    completed_sp = df_completed['_sp'].sum()
    remaining_sp = df_remaining['_sp'].sum()
    total_sp = completed_sp + remaining_sp
    
    # =========================================================================
    # DISPLAY RESULTS - STORY POINTS
    # =========================================================================
    if show_story_points:
        st.header("🎯 Story Points Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "✅ Completed", 
                f"{completed_sp:.1f} SP",
                help="Story points for tickets in UAT, Done, Released, Resolved, Closed, On Production, or Pending Unleash stage"
            )
            st.caption(f"{len(df_completed)} tickets")
        
        with col2:
            st.metric(
                "⏳ Remaining", 
                f"{remaining_sp:.1f} SP",
                help="Story points for tickets not yet in UAT, Done, Released, Resolved, Closed, On Production, or Pending Unleash"
            )
            st.caption(f"{len(df_remaining)} tickets")
        
        with col3:
            st.metric(
                "📊 Total", 
                f"{total_sp:.1f} SP",
                help="Total story points (completed + remaining)"
            )
            st.caption(f"{len(df_active)} active tickets")
        
        # Progress bar
        if total_sp > 0:
            progress = completed_sp / total_sp
            st.progress(progress, text=f"Sprint Progress: {progress:.1%}")
        
        # Pie chart showing tickets by Type
        if 'Type' in df_active.columns and len(df_active) > 0:
            type_counts = df_active['Type'].value_counts()
            if len(type_counts) > 0:
                import plotly.express as px
                
                # Create pie chart
                fig = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    title="Tickets by Type",
                    hole=0.4,  # Donut chart style
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig.update_traces(
                    textinfo='percent+label',
                    textposition='outside',
                    hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
                )
                fig.update_layout(
                    height=400,
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="middle",
                        y=0.5,
                        xanchor="left",
                        x=1.05
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # Show remaining tickets
        if len(df_remaining) > 0:
            with st.expander(f"⏳ Click to view {len(df_remaining)} remaining tickets ({remaining_sp:.1f} SP)"):
                display_tickets_table(df_remaining, ['ID', 'Link', 'Name', 'Type', 'StoryPoints', 'Stage', 'AssigneeName'])
        
        # Show completed tickets
        if len(df_completed) > 0:
            with st.expander(f"✅ Click to view {len(df_completed)} completed tickets ({completed_sp:.1f} SP)"):
                display_tickets_table(df_completed, ['ID', 'Link', 'Name', 'Type', 'StoryPoints', 'Stage', 'AssigneeName'])
        
        st.divider()
    
    # =========================================================================
    # DORA METRICS
    # =========================================================================
    if show_dora:
        st.header("🚀 DORA Metrics")
        st.caption("DevOps Research and Assessment - Software Delivery Performance")
        
        # Show DORA explanation
        with st.expander("ℹ️ What are DORA Metrics?"):
            st.markdown("""
            **DORA (DevOps Research and Assessment)** metrics are the gold standard for measuring software delivery performance:
            
            | Metric | What it measures | Formula |
            |--------|------------------|---------|
            | **Deployment Frequency** | How often you deploy to production | Count of tickets reaching "On Production" |
            | **Lead Time for Changes** | Time from commit to production | `On_Production_start - In_Progress_start` |
            | **Change Failure Rate** | % of deployments causing rework | `(QA_recurrence + UAT_recurrence) / Deployments` |
            | **Mean Time to Restore** | How fast you fix production issues | `Resolved_start - On_Production_start` |
            
            Higher deployment frequency and lower lead times indicate elite performance.
            """)
        
        # Calculate DORA summary
        dora_summary = calculate_dora_summary(df_active, sprint_duration_days=14)
        overall_rating, overall_color = get_overall_dora_rating(dora_summary)
        
        # Overall DORA Score
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                border-left: 4px solid {overall_color};
                padding: 16px 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            ">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <span style="font-size: 1.2em; color: #e2e8f0;">Overall DORA Performance</span>
                    </div>
                    <div style="
                        background: {overall_color};
                        color: white;
                        padding: 8px 20px;
                        border-radius: 25px;
                        font-weight: bold;
                        font-size: 1.1em;
                    ">{overall_rating}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # ----- 1. DEPLOYMENT FREQUENCY -----
        st.subheader("📦 Deployment Frequency")
        
        df_stats = dora_summary['deployment_frequency']['stats']
        df_rating = dora_summary['deployment_frequency']['rating']
        df_color = dora_summary['deployment_frequency']['color']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🚀 Deployments",
                f"{df_stats['total_deployments']}",
                help="Total tickets deployed to production"
            )
            st.markdown(
                f"<span style='background:{df_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{df_rating}</span>",
                unsafe_allow_html=True
            )
        
        with col2:
            st.metric(
                "📅 Per Week",
                f"{df_stats['deployments_per_week']:.1f}",
                help="Average deployments per week"
            )
        
        with col3:
            st.metric(
                "📊 Per Day",
                f"{df_stats['deployments_per_day']:.2f}",
                help="Average deployments per day"
            )
        
        with col4:
            st.metric(
                "📈 Deploy Rate",
                f"{df_stats['deployment_percentage']:.1f}%",
                help="Percentage of tickets that reached production"
            )
        
        # Deployment frequency by type
        df_by_type = deployment_frequency_by_type(df_active)
        if len(df_by_type) > 0:
            with st.expander("📊 Deployment Frequency by Type"):
                st.dataframe(
                    df_by_type,
                    column_config={
                        "Type": st.column_config.TextColumn("Type"),
                        "Total Tickets": st.column_config.NumberColumn("Total"),
                        "Deployed": st.column_config.NumberColumn("Deployed"),
                        "Deployment Rate": st.column_config.NumberColumn("Rate %"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
        
        # Show deployed tickets
        deployed_tickets = get_deployments(df_active)
        if len(deployed_tickets) > 0:
            with st.expander(f"✅ View {len(deployed_tickets)} Deployed Tickets"):
                display_tickets_table(deployed_tickets, ['ID', 'Link', 'Name', 'Type', 'StoryPoints', 'AssigneeName'])
        
        st.divider()
        
        # ----- 2. LEAD TIME FOR CHANGES -----
        st.subheader("⏱️ Lead Time for Changes")
        st.caption("Time from development start to production deployment")
        
        ltc_stats = dora_summary['lead_time_for_changes']['stats']
        ltc_rating = dora_summary['lead_time_for_changes']['rating']
        ltc_color = dora_summary['lead_time_for_changes']['color']
        
        if ltc_stats['count'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "📏 Median",
                    f"{ltc_stats['median']:.1f} days",
                    help="Median time from In Progress to On Production"
                )
                st.markdown(
                    f"<span style='background:{ltc_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{ltc_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "📈 Average",
                    f"{ltc_stats['mean']:.1f} days",
                    help="Average lead time for changes"
                )
            
            with col3:
                st.metric(
                    "🔺 P90",
                    f"{ltc_stats['p90']:.1f} days",
                    help="90th percentile lead time"
                )
            
            with col4:
                st.metric(
                    "📋 Measured",
                    f"{ltc_stats['count']}",
                    help="Tickets with lead time data"
                )
            
            # Lead time by type
            ltc_by_type = lead_time_for_changes_by_type(df_active)
            if len(ltc_by_type) > 0:
                with st.expander("📊 Lead Time by Type"):
                    st.dataframe(
                        ltc_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median": st.column_config.NumberColumn("Median (days)"),
                            "Mean": st.column_config.NumberColumn("Mean (days)"),
                            "P90": st.column_config.NumberColumn("P90 (days)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No lead time data available. Tickets need 'In Progress' and 'On Production' stage dates.")
        
        st.divider()
        
        # ----- 3. CHANGE FAILURE RATE -----
        st.subheader("⚠️ Change Failure Rate")
        st.caption("Percentage of deployments causing rework (QA/UAT recurrence)")
        
        cfr_stats = dora_summary['change_failure_rate']['stats']
        cfr_rating = dora_summary['change_failure_rate']['rating']
        cfr_color = dora_summary['change_failure_rate']['color']
        
        if cfr_stats['total_deployments'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "📉 CFR",
                    f"{cfr_stats['change_failure_rate']:.1f}%",
                    help="Change Failure Rate = (QA + UAT recurrence) / Deployments"
                )
                st.markdown(
                    f"<span style='background:{cfr_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{cfr_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "🔄 Failure Signals",
                    f"{cfr_stats['total_failure_signals']}",
                    help="Total QA + UAT recurrence count"
                )
            
            with col3:
                st.metric(
                    "🧪 QA Bounces",
                    f"{cfr_stats['qa_recurrence_total']}",
                    help="Total QA stage recurrence"
                )
            
            with col4:
                st.metric(
                    "✅ UAT Bounces",
                    f"{cfr_stats['uat_recurrence_total']}",
                    help="Total UAT stage recurrence"
                )
            
            # CFR by type
            cfr_by_type = change_failure_rate_by_type(df_active)
            if len(cfr_by_type) > 0:
                with st.expander("📊 Change Failure Rate by Type"):
                    st.dataframe(
                        cfr_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Deployments": st.column_config.NumberColumn("Deployments"),
                            "Failure Signals": st.column_config.NumberColumn("Failures"),
                            "CFR (%)": st.column_config.NumberColumn("CFR %"),
                            "Tickets w/ Failures": st.column_config.NumberColumn("Affected"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show tickets with failures
            failed_tickets = get_tickets_with_failures(df_active)
            if len(failed_tickets) > 0:
                with st.expander(f"⚠️ View {len(failed_tickets)} Tickets with Failures"):
                    fail_cols = ['ID', 'Link', 'Name', 'Type', 'Failure_Signals']
                    available_cols = [c for c in fail_cols if c in failed_tickets.columns]
                    st.dataframe(
                        failed_tickets[available_cols].head(20),
                        column_config={
                            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                            "Failure_Signals": st.column_config.NumberColumn("Failures"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No deployment data available for CFR calculation.")
        
        st.divider()
        
        # ----- 4. MEAN TIME TO RESTORE -----
        st.subheader("🔧 Mean Time to Restore (MTTR)")
        st.caption("Time from production deployment to resolution")
        
        mttr_data = dora_summary['mttr']['stats']
        mttr_rating = dora_summary['mttr']['rating']
        mttr_color = dora_summary['mttr']['color']
        
        if mttr_data['count'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "⏱️ Median MTTR",
                    format_hours_human(mttr_data['median_hours']),
                    help="Median time from On Production to Resolved"
                )
                st.markdown(
                    f"<span style='background:{mttr_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{mttr_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "📈 Average",
                    format_hours_human(mttr_data['mean_hours']),
                    help="Average MTTR"
                )
            
            with col3:
                st.metric(
                    "🔺 P90",
                    format_hours_human(mttr_data['p90_hours']),
                    help="90th percentile MTTR"
                )
            
            with col4:
                st.metric(
                    "📋 Measured",
                    f"{mttr_data['count']}",
                    help="Tickets with MTTR data"
                )
            
            # MTTR by type
            mttr_type = mttr_by_type(df_active)
            if len(mttr_type) > 0:
                with st.expander("📊 MTTR by Type"):
                    st.dataframe(
                        mttr_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median (hours)": st.column_config.NumberColumn("Median (h)"),
                            "Mean (hours)": st.column_config.NumberColumn("Mean (h)"),
                            "Median (days)": st.column_config.NumberColumn("Median (d)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # MTTR by priority
            mttr_prio = mttr_by_priority(df_active)
            if len(mttr_prio) > 0:
                with st.expander("📊 MTTR by Priority"):
                    st.dataframe(
                        mttr_prio,
                        column_config={
                            "Priority": st.column_config.TextColumn("Priority"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median (hours)": st.column_config.NumberColumn("Median (h)"),
                            "Mean (hours)": st.column_config.NumberColumn("Mean (h)"),
                            "P90 (hours)": st.column_config.NumberColumn("P90 (h)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show MTTR tickets
            mttr_tickets = get_tickets_with_mttr(df_active)
            if len(mttr_tickets) > 0:
                with st.expander(f"🔧 View {len(mttr_tickets)} Tickets with MTTR Data"):
                    mttr_cols = ['ID', 'Link', 'Name', 'Type', 'MTTR_Hours']
                    available_cols = [c for c in mttr_cols if c in mttr_tickets.columns]
                    display_df = mttr_tickets[available_cols].head(20).copy()
                    display_df['MTTR_Display'] = display_df['MTTR_Hours'].apply(format_hours_human)
                    st.dataframe(
                        display_df.drop(columns=['MTTR_Hours'], errors='ignore'),
                        column_config={
                            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                            "MTTR_Display": st.column_config.TextColumn("MTTR"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No MTTR data available. Tickets need 'On Production' and 'Resolved' stage dates.")
        
        # DORA Benchmarks reference
        with st.expander("📋 DORA Benchmarks Reference"):
            st.markdown("""
            | Metric | Elite | High | Medium | Low |
            |--------|-------|------|--------|-----|
            | **Deployment Frequency** | On-demand / daily | Weekly | Monthly | Quarterly |
            | **Lead Time for Changes** | < 1 day | 1-7 days | 1-4 weeks | > 1 month |
            | **Change Failure Rate** | 0-15% | — | 16-30% | > 30% |
            | **MTTR** | < 1 hour | < 1 day | 1-7 days | > 1 week |
            """)
        
        st.divider()
    
    # =========================================================================
    # STAGE TIME ANALYSIS
    # =========================================================================
    if show_stage_time:
        st.header("📊 Stage Time Analysis")
        st.caption("Time spent in each workflow stage (identifies bottlenecks)")
        
        # Stage category filter
        col1, col2 = st.columns([2, 1])
        with col1:
            stage_category = st.selectbox(
                "Filter by Stage Category",
                options=['All Stages'] + list(STAGE_CATEGORIES.keys()),
                index=0,
                help="Filter stages by category"
            )
        with col2:
            chart_type = st.radio("Chart Type", ["Bar", "Pie"], horizontal=True)
        
        # Get chart data
        if stage_category == 'All Stages':
            chart_data = get_stage_time_chart_data(df_active)
        else:
            chart_data = get_stage_time_chart_data(df_active, category=stage_category)
        
        if len(chart_data) > 0:
            import plotly.express as px
            
            # Total time summary
            total_stage_time = chart_data['Total Days'].sum()
            total_tickets_with_stage = chart_data['Tickets'].sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total Time in Stages", f"{total_stage_time:.1f} days")
            with col2:
                top_stage = chart_data.iloc[0]['Stage'] if len(chart_data) > 0 else "N/A"
                st.metric("🔥 Top Stage", top_stage)
            with col3:
                st.metric("📈 Stages with Data", len(chart_data))
            
            # Create chart
            if chart_type == "Bar":
                fig = px.bar(
                    chart_data.head(12),  # Top 12 stages
                    x='Stage',
                    y='Total Days',
                    color='Avg Days',
                    color_continuous_scale='RdYlGn_r',  # Red = slow, Green = fast
                    title=f"Time Spent in Stages ({stage_category})",
                    hover_data=['Tickets', 'Avg Days']
                )
                fig.update_layout(
                    xaxis_tickangle=-45,
                    height=450,
                    coloraxis_colorbar_title="Avg Days"
                )
            else:
                fig = px.pie(
                    chart_data.head(10),  # Top 10 for pie
                    values='Total Days',
                    names='Stage',
                    title=f"Stage Time Distribution ({stage_category})",
                    hole=0.4
                )
                fig.update_traces(textinfo='percent+label')
                fig.update_layout(height=450)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Bottleneck analysis
            with st.expander("🔥 Top Bottlenecks (by average time)"):
                bottlenecks = get_stage_bottlenecks(df_active, top_n=5)
                if len(bottlenecks) > 0:
                    st.dataframe(
                        bottlenecks,
                        column_config={
                            "Stage": st.column_config.TextColumn("Stage"),
                            "Avg Days": st.column_config.NumberColumn("Avg Days", format="%.2f"),
                            "Median Days": st.column_config.NumberColumn("Median Days", format="%.2f"),
                            "Tickets Affected": st.column_config.NumberColumn("Tickets"),
                            "Total Days": st.column_config.NumberColumn("Total Days", format="%.1f"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Full stage breakdown
            with st.expander("📋 Full Stage Breakdown"):
                stage_summary = get_stage_time_summary(df_active)
                if len(stage_summary) > 0:
                    st.dataframe(
                        stage_summary,
                        column_config={
                            "Stage": st.column_config.TextColumn("Stage"),
                            "Tickets": st.column_config.NumberColumn("Tickets"),
                            "Total Days": st.column_config.NumberColumn("Total Days", format="%.1f"),
                            "Avg Days": st.column_config.NumberColumn("Avg Days", format="%.2f"),
                            "Median Days": st.column_config.NumberColumn("Median Days", format="%.2f"),
                            "Max Days": st.column_config.NumberColumn("Max Days", format="%.1f"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No stage time data available.")
        
        st.divider()
    
    # =========================================================================
    # CYCLE TIME ANALYSIS
    # =========================================================================
    # Calculate cycle time for all active tickets (needed for Standout Tickets)
    df_active['Cycle_Time'] = calculate_cycle_time(df_active)
    
    if show_cycle_time:
        st.header("⏱️ Cycle Time Analysis")
        st.caption("Time from **In Progress** → **Done/UAT/Resolved** (measures engineering velocity)")
        
        # Get stats
        stats = cycle_time_stats(df_active)
        
        if stats['count'] > 0:
            # Get rating
            rating, rating_color = get_cycle_time_rating(stats['median'])
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "📊 Median",
                    f"{stats['median']:.1f} days",
                    help="Median cycle time - 50% of tickets complete faster than this"
                )
                st.markdown(
                    f"<span style='background:{rating_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "📈 Average",
                    f"{stats['mean']:.1f} days",
                    help="Average cycle time across all completed tickets"
                )
            
            with col3:
                st.metric(
                    "🔺 90th Percentile",
                    f"{stats['p90']:.1f} days",
                    help="90% of tickets complete within this time"
                )
            
            with col4:
                st.metric(
                    "📋 Tickets Measured",
                    f"{stats['count']}",
                    help="Number of tickets with calculable cycle time"
                )
            
            # Cycle time by type
            ct_by_type = cycle_time_by_type(df_active)
            if len(ct_by_type) > 0:
                with st.expander("📊 Cycle Time by Type"):
                    st.dataframe(
                        ct_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median": st.column_config.NumberColumn("Median (days)"),
                            "Mean": st.column_config.NumberColumn("Mean (days)"),
                            "P90": st.column_config.NumberColumn("P90 (days)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show outliers (slow tickets)
            outliers = identify_outliers(df_active, threshold_percentile=90)
            if len(outliers) > 0:
                with st.expander(f"🐢 Slow Tickets (>{stats['p90']:.1f} days) - {len(outliers)} tickets"):
                    outlier_cols = ['ID', 'Link', 'Name', 'Type', 'Cycle_Time', 'Stage', 'AssigneeName']
                    available_cols = [c for c in outlier_cols if c in outliers.columns]
                    st.dataframe(
                        outliers[available_cols],
                        column_config={
                            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                            "Cycle_Time": st.column_config.NumberColumn("Cycle Time (days)", format="%.1f"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No cycle time data available. Tickets need 'In Progress' start and completion dates.")
        
        st.divider()
    
    # =========================================================================
    # LEAD TIME ANALYSIS
    # =========================================================================
    # Calculate lead time for all active tickets (needed for Standout Tickets)
    df_active['Lead_Time'] = calculate_lead_time(df_active)
    df_active['Wait_Time'] = calculate_wait_time(df_active)
    
    if show_lead_time:
        st.header("📏 Lead Time Analysis")
        st.caption("Time from **New** → **Done/UAT/Resolved** (total delivery latency including planning)")
        
        # Get stats
        lt_stats = lead_time_stats(df_active)
        
        if lt_stats['count'] > 0:
            # Get rating
            lt_rating, lt_rating_color = get_lead_time_rating(lt_stats['median'])
            
            # Calculate average wait time
            wait_valid = pd.to_numeric(df_active['Wait_Time'], errors='coerce').dropna()
            avg_wait = round(wait_valid.mean(), 1) if len(wait_valid) > 0 else 0
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "📏 Median Lead Time",
                    f"{lt_stats['median']:.1f} days",
                    help="Median lead time - total time from New to Done"
                )
                st.markdown(
                    f"<span style='background:{lt_rating_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{lt_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "📈 Average Lead Time",
                    f"{lt_stats['mean']:.1f} days",
                    help="Average lead time across all completed tickets"
                )
            
            with col3:
                st.metric(
                    "⏳ Avg Wait Time",
                    f"{avg_wait:.1f} days",
                    help="Average time from New → In Progress (planning/queue overhead)"
                )
            
            with col4:
                st.metric(
                    "🔺 90th Percentile",
                    f"{lt_stats['p90']:.1f} days",
                    help="90% of tickets complete within this time"
                )
            
            # Show breakdown: Wait Time vs Cycle Time
            ct_stats = cycle_time_stats(df_active)
            if ct_stats['count'] > 0 and avg_wait > 0:
                total_time = avg_wait + ct_stats['mean']
                wait_pct = (avg_wait / total_time * 100) if total_time > 0 else 0
                dev_pct = 100 - wait_pct
                
                st.caption(f"⏱️ **Time Breakdown:** Wait/Planning: {wait_pct:.0f}% | Development: {dev_pct:.0f}%")
            
            # Lead time by type
            lt_by_type = lead_time_by_type(df_active)
            if len(lt_by_type) > 0:
                with st.expander("📊 Lead Time by Type"):
                    st.dataframe(
                        lt_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median": st.column_config.NumberColumn("Median (days)"),
                            "Mean": st.column_config.NumberColumn("Mean (days)"),
                            "P90": st.column_config.NumberColumn("P90 (days)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No lead time data available. Tickets need 'New' start and completion dates.")
        
        st.divider()
    
    # Calculate flow efficiency metrics (used by Standout Tickets selector)
    df_active['Flow_Efficiency'] = calculate_flow_efficiency(df_active)
    df_active['Active_Time'] = calculate_active_time(df_active)
    df_active['Waiting_Time_Total'] = calculate_waiting_time(df_active)
    
    # =========================================================================
    # HANDOFF DELAY ANALYSIS
    # =========================================================================
    # Calculate handoff delays (needed for Standout Tickets)
    df_active['Handoff_Dev_QA_Ready'] = calculate_dev_to_qa_ready_delay(df_active)
    df_active['Handoff_QA_Ready_QA'] = calculate_qa_ready_to_qa_delay(df_active)
    df_active['Handoff_Total'] = calculate_total_handoff_delay(df_active)
    
    if show_handoff_delay:
        st.header("🤝 Handoff Delay Analysis")
        st.caption("Time lost during stage transitions (Dev → QA Ready → QA)")
        
        # Get stats
        ho_stats = handoff_delay_stats(df_active)
        
        if ho_stats['total_count'] > 0:
            # Get rating based on total median
            ho_rating, ho_rating_color = get_handoff_delay_rating(ho_stats['total_median'])
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "🤝 Median Total Delay",
                    f"{ho_stats['total_median']:.1f} days",
                    help="Median combined handoff delay across all transitions"
                )
                st.markdown(
                    f"<span style='background:{ho_rating_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{ho_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "⏱️ Dev → QA Ready",
                    f"{ho_stats['dev_qa_ready_median']:.1f} days",
                    help="Median time from dev completion to QA ready status"
                )
                st.caption(f"{ho_stats['dev_qa_ready_count']} tickets")
            
            with col3:
                st.metric(
                    "⏳ QA Ready → QA",
                    f"{ho_stats['qa_ready_qa_median']:.1f} days",
                    help="Median time waiting for QA to start after marked ready"
                )
                st.caption(f"{ho_stats['qa_ready_qa_count']} tickets")
            
            with col4:
                st.metric(
                    "📊 Total Days Lost",
                    f"{ho_stats['total_total']:.1f}",
                    help="Total days lost to handoff delays across all tickets"
                )
                st.caption(f"{ho_stats['total_count']} tickets affected")
            
            # Handoff breakdown
            ho_breakdown = handoff_breakdown(df_active)
            if len(ho_breakdown) > 0:
                with st.expander("📊 Handoff Breakdown by Transition"):
                    st.caption("Where are handoffs slowing down?")
                    st.dataframe(
                        ho_breakdown,
                        column_config={
                            "Transition": st.column_config.TextColumn("Transition"),
                            "Total Days": st.column_config.NumberColumn("Total Days"),
                            "Tickets Affected": st.column_config.NumberColumn("Tickets"),
                            "Median": st.column_config.NumberColumn("Median (days)"),
                            "Mean": st.column_config.NumberColumn("Mean (days)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Handoff delay by type
            ho_by_type = handoff_delay_by_type(df_active)
            if len(ho_by_type) > 0:
                with st.expander("📊 Handoff Delay by Type"):
                    st.dataframe(
                        ho_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median": st.column_config.NumberColumn("Median (days)"),
                            "Mean": st.column_config.NumberColumn("Mean (days)"),
                            "P90": st.column_config.NumberColumn("P90 (days)"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show worst handoff tickets
            worst_handoffs = df_active[df_active['Handoff_Total'].notna()].copy()
            worst_handoffs = worst_handoffs[worst_handoffs['Handoff_Total'] > 0]
            worst_handoffs = worst_handoffs.nlargest(10, 'Handoff_Total')
            
            if len(worst_handoffs) > 0:
                with st.expander(f"🐢 Slowest Handoffs (Top {len(worst_handoffs)} tickets)"):
                    handoff_cols = ['ID', 'Link', 'Name', 'Type', 'Handoff_Total', 'Handoff_Dev_QA_Ready', 'Handoff_QA_Ready_QA']
                    available_cols = [c for c in handoff_cols if c in worst_handoffs.columns]
                    st.dataframe(
                        worst_handoffs[available_cols],
                        column_config={
                            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                            "Handoff_Total": st.column_config.NumberColumn("Total Delay (days)", format="%.1f"),
                            "Handoff_Dev_QA_Ready": st.column_config.NumberColumn("Dev→QA Ready", format="%.1f"),
                            "Handoff_QA_Ready_QA": st.column_config.NumberColumn("QA Ready→QA", format="%.1f"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No handoff delay data available. Tickets need 'In Progress', 'QA Ready', and 'QA' stage data.")
        
        st.divider()
    
    # =========================================================================
    # QUALITY & STABILITY KPIs - RECURRENCE RATE
    # =========================================================================
    # Calculate recurrence metrics (needed for Standout Tickets)
    df_active['Total_Recurrence'] = calculate_recurrence_count(df_active)
    # Calculate defect escapes (needed for Standout Tickets)
    df_active['Is_Escape'] = calculate_defect_escape(df_active)
    
    if show_quality:
        st.header("🔄 Quality & Stability")
        st.caption("Bounce-back rates measuring code quality and requirement clarity")
        
        # Show calculation info
        with st.expander("ℹ️ How is this calculated?"):
            st.markdown("""
            **Bounce-back Detection:**
            - `recurrence = 1` means ticket entered stage **once** (normal flow, first time)
            - `recurrence > 1` means ticket **re-entered** the stage (actual bounce-back)
            
            **Example:** If QA recurrence = 2, ticket went to QA twice → bounced back once after failing.
            
            **Bounce Rate** = (tickets with recurrence > 1) / total tickets × 100%
            """)
        
        # Get stats
        rec_stats = recurrence_stats(df_active)
        
        if rec_stats['total_tickets'] > 0:
            # Get rating based on overall recurrence rate
            rec_rating, rec_rating_color = get_recurrence_rating(rec_stats['overall_rate'])
            
            # Display main metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "🔄 Overall Recurrence Rate",
                    f"{rec_stats['overall_rate']:.1f}%",
                    help="Percentage of tickets that bounced back at least once"
                )
                st.markdown(
                    f"<span style='background:{rec_rating_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{rec_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "🧪 QA Recurrence",
                    f"{rec_stats['qa_rate']:.1f}%",
                    help="Tickets that bounced back from QA"
                )
                st.caption(f"{rec_stats['qa_tickets']} tickets ({rec_stats['qa_total']} bounces)")
            
            with col3:
                st.metric(
                    "✅ UAT Recurrence",
                    f"{rec_stats['uat_rate']:.1f}%",
                    help="Tickets that bounced back from UAT"
                )
                st.caption(f"{rec_stats['uat_tickets']} tickets ({rec_stats['uat_total']} bounces)")
            
            with col4:
                st.metric(
                    "❌ Rejected Recurrence",
                    f"{rec_stats['rejected_rate']:.1f}%",
                    help="Tickets that were rejected and returned"
                )
                st.caption(f"{rec_stats['rejected_tickets']} tickets ({rec_stats['rejected_total']} bounces)")
            
            # Summary stats row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "📊 Tickets with Recurrence",
                    f"{rec_stats['tickets_with_recurrence']}",
                    help="Total tickets that bounced back at least once"
                )
            with col2:
                st.metric(
                    "🔢 Total Bounces",
                    f"{rec_stats['total_recurrence_count']}",
                    help="Total number of times tickets bounced back"
                )
            with col3:
                st.metric(
                    "📉 Avg Bounces/Ticket",
                    f"{rec_stats['avg_recurrence_per_ticket']:.2f}",
                    help="Average recurrence count across all tickets"
                )
            
            # Recurrence breakdown by stage
            rec_breakdown = recurrence_breakdown(df_active)
            if len(rec_breakdown) > 0:
                with st.expander("📊 Recurrence Breakdown by Stage"):
                    st.caption("Which stages are causing the most rework?")
                    st.dataframe(
                        rec_breakdown,
                        column_config={
                            "Stage": st.column_config.TextColumn("Stage"),
                            "Tickets Affected": st.column_config.NumberColumn("Tickets"),
                            "Total Bounces": st.column_config.NumberColumn("Total Bounces"),
                            "Rate (%)": st.column_config.NumberColumn("Rate %"),
                            "Avg Bounces/Ticket": st.column_config.NumberColumn("Avg/Ticket"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Recurrence by type
            rec_by_type = recurrence_by_type(df_active)
            if len(rec_by_type) > 0:
                with st.expander("📊 Recurrence by Ticket Type"):
                    st.dataframe(
                        rec_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Total Tickets": st.column_config.NumberColumn("Total"),
                            "With Recurrence": st.column_config.NumberColumn("With Recurrence"),
                            "Recurrence Rate": st.column_config.NumberColumn("Rate %"),
                            "Total Bounces": st.column_config.NumberColumn("Bounces"),
                            "Avg Bounces": st.column_config.NumberColumn("Avg Bounces"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show tickets that bounced back
            high_recurrence = identify_high_recurrence_tickets(df_active, min_bounces=1)
            if len(high_recurrence) > 0:
                with st.expander(f"🔁 Bounced Tickets ({len(high_recurrence)} tickets that bounced back)"):
                    rec_cols = ['ID', 'Link', 'Name', 'Type', 'Total_Recurrence', 'QA_Recurrence', 'UAT_Recurrence', 'Rejected_Recurrence']
                    available_cols = [c for c in rec_cols if c in high_recurrence.columns]
                    st.dataframe(
                        high_recurrence[available_cols].head(15),
                        column_config={
                            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                            "Total_Recurrence": st.column_config.NumberColumn("Total Bounces"),
                            "QA_Recurrence": st.column_config.NumberColumn("QA Bounces"),
                            "UAT_Recurrence": st.column_config.NumberColumn("UAT Bounces"),
                            "Rejected_Recurrence": st.column_config.NumberColumn("Rejected"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No recurrence data available.")
        
        # ----- Defect Escape Rate Sub-section -----
        # st.subheader("🚨 Defect Escape Rate")
        # st.caption("Defects that passed QA but were caught in UAT/Production")
        # 
        # # Get stats
        # esc_stats = defect_escape_stats(df_active)
        # 
        # if esc_stats['tickets_reached_uat'] > 0:
        #     # Get rating
        #     esc_rating, esc_rating_color = get_escape_rate_rating(esc_stats['escape_rate'])
        #     
        #     # Display metrics
        #     col1, col2, col3, col4 = st.columns(4)
        #     
        #     with col1:
        #         st.metric(
        #             "🚨 Escape Rate",
        #             f"{esc_stats['escape_rate']:.1f}%",
        #             help="Percentage of UAT+ tickets that escaped QA and were sent back"
        #         )
        #         st.markdown(
        #             f"<span style='background:{esc_rating_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{esc_rating}</span>",
        #             unsafe_allow_html=True
        #         )
        #     
        #     with col2:
        #         st.metric(
        #             "🎯 Tickets Reached UAT+",
        #             f"{esc_stats['tickets_reached_uat']}",
        #             help="Tickets that reached UAT, Done, or Production stages"
        #         )
        #     
        #     with col3:
        #         st.metric(
        #             "🔙 Escaped Defects",
        #             f"{esc_stats['escaped_defects']}",
        #             help="Tickets that reached UAT+ then were sent back"
        #         )
        #     
        #     with col4:
        #         st.metric(
        #             "📊 Overall Rate",
        #             f"{esc_stats['overall_rate']:.1f}%",
        #             help="Escape rate across all tickets (not just UAT+)"
        #         )
        #     
        #     # Escape breakdown (where defects were caught)
        #     esc_breakdown = defect_escape_breakdown(df_active)
        #     if len(esc_breakdown) > 0:
        #         with st.expander("📊 Where Escaped Defects Were Caught"):
        #             st.caption("Which stage caught the defects after they escaped QA?")
        #             st.dataframe(
        #                 esc_breakdown,
        #                 column_config={
        #                     "Caught At": st.column_config.TextColumn("Caught At"),
        #                     "Tickets": st.column_config.NumberColumn("Tickets"),
        #                     "Percentage": st.column_config.NumberColumn("% of Escapes"),
        #                 },
        #                 hide_index=True,
        #                 use_container_width=True
        #             )
        #     
        #     # Escape by type
        #     esc_by_type = defect_escape_by_type(df_active)
        #     if len(esc_by_type) > 0:
        #         with st.expander("📊 Defect Escape by Ticket Type"):
        #             st.dataframe(
        #                 esc_by_type,
        #                 column_config={
        #                     "Type": st.column_config.TextColumn("Type"),
        #                     "Total Tickets": st.column_config.NumberColumn("Total"),
        #                     "Escaped": st.column_config.NumberColumn("Escaped"),
        #                     "Escape Rate": st.column_config.NumberColumn("Escape Rate %"),
        #                 },
        #                 hide_index=True,
        #                 use_container_width=True
        #             )
        #     
        #     # Show escaped defect tickets
        #     escaped_tickets = identify_escaped_defects(df_active)
        #     if len(escaped_tickets) > 0:
        #         with st.expander(f"🚨 Escaped Defect Tickets ({len(escaped_tickets)} tickets)"):
        #             esc_cols = ['ID', 'Link', 'Name', 'Type', 'Rejected_After_UAT', 'QA_Retest', 'Rework']
        #             available_cols = [c for c in esc_cols if c in escaped_tickets.columns]
        #             st.dataframe(
        #                 escaped_tickets[available_cols].head(20),
        #                 column_config={
        #                     "Link": st.column_config.LinkColumn("Link", display_text="Open"),
        #                     "Rejected_After_UAT": st.column_config.NumberColumn("Rejected"),
        #                     "QA_Retest": st.column_config.NumberColumn("QA Re-test"),
        #                     "Rework": st.column_config.NumberColumn("Rework"),
        #                 },
        #                 hide_index=True,
        #                 use_container_width=True
        #             )
        # else:
        #     st.info("ℹ️ No defect escape data available. Tickets need UAT/Done stage data.")
        
        st.subheader("🚨 Defect Escape Rate Disabled")
        
        st.divider()
    
    # =========================================================================
    # ESTIMATION ACCURACY (Team Maturity KPI)
    # =========================================================================
    # Calculate estimation accuracy (needed for Standout Tickets)
    df_active['Estimation_Accuracy'] = calculate_estimation_accuracy(df_active)
    
    if show_estimation:
        st.header("🎯 Estimation Accuracy")
        st.caption("Actual dev time vs Story Points estimate (1 SP = 8 hours)")
        
        # Show formula
        with st.expander("ℹ️ How is this calculated?"):
            st.markdown("""
            **Formula:** `Estimation Accuracy = Actual Time / Estimated Time`
            
            Where:
            - **Estimated Time** = Story Points × 8 hours (1 SP = 1 day = 8 work hours)
            - **Actual Time** = Time from "In Progress" to "UAT" start (converted to work hours)
            
            **Interpretation:**
            - **1.0** = Perfect estimation (actual = estimate)
            - **< 1.0** = Overestimated (finished faster than expected)
            - **> 1.0** = Underestimated (took longer than expected)
            """)
        
        # Get stats
        est_stats = estimation_accuracy_stats(df_active)
        
        if est_stats['count'] > 0:
            # Get rating
            est_rating, est_rating_color = get_estimation_accuracy_rating(est_stats['median'])
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "🎯 Median Accuracy",
                    f"{est_stats['median']:.2f}x",
                    help="Median ratio of time spent vs estimated (1.0 = perfect)"
                )
                st.markdown(
                    f"<span style='background:{est_rating_color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold;font-size:0.8em'>{est_rating}</span>",
                    unsafe_allow_html=True
                )
            
            with col2:
                st.metric(
                    "✅ Accurate",
                    f"{est_stats['accurate_pct']:.0f}%",
                    help="Tickets within ±20% of estimate (0.8-1.2x)"
                )
                st.caption(f"{est_stats['accurate_count']} tickets")
            
            with col3:
                st.metric(
                    "📈 Underestimated",
                    f"{est_stats['underestimated_pct']:.0f}%",
                    help="Tickets that took longer than estimated (>1.2x)"
                )
                st.caption(f"{est_stats['underestimated_count']} tickets")
            
            with col4:
                st.metric(
                    "📉 Overestimated",
                    f"{est_stats['overestimated_pct']:.0f}%",
                    help="Tickets that finished faster than estimated (<0.8x)"
                )
                st.caption(f"{est_stats['overestimated_count']} tickets")
            
            # Visual breakdown
            accurate_pct = est_stats['accurate_pct']
            st.progress(accurate_pct / 100, text=f"Estimation Accuracy: {accurate_pct:.0f}% of tickets within ±20% of estimate")
            
            # Estimation by type
            est_by_type = estimation_accuracy_by_type(df_active)
            if len(est_by_type) > 0:
                with st.expander("📊 Estimation Accuracy by Type"):
                    st.caption("Which ticket types are estimated most accurately?")
                    st.dataframe(
                        est_by_type,
                        column_config={
                            "Type": st.column_config.TextColumn("Type"),
                            "Count": st.column_config.NumberColumn("Count"),
                            "Median": st.column_config.NumberColumn("Median Ratio"),
                            "Mean": st.column_config.NumberColumn("Mean Ratio"),
                            "Accurate %": st.column_config.NumberColumn("Accurate %"),
                            "Underestimated %": st.column_config.NumberColumn("Underestimated %"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
            
            # Show worst estimation tickets
            est_outliers = identify_estimation_outliers(df_active, threshold=2.0)
            if len(est_outliers) > 0:
                with st.expander(f"⚠️ Estimation Outliers ({len(est_outliers)} tickets with >2x error)"):
                    st.caption("Tickets significantly over or under estimated")
                    
                    # Add formatted columns
                    est_outliers_display = est_outliers.copy()
                    if 'Timeoriginalestimate' in est_outliers_display.columns:
                        est_outliers_display['Est_Display'] = est_outliers_display['Timeoriginalestimate'].apply(
                            lambda x: format_time_seconds(pd.to_numeric(x, errors='coerce'))
                        )
                    if 'Timespent' in est_outliers_display.columns:
                        est_outliers_display['Spent_Display'] = est_outliers_display['Timespent'].apply(
                            lambda x: format_time_seconds(pd.to_numeric(x, errors='coerce'))
                        )
                    
                    outlier_cols = ['ID', 'Link', 'Name', 'Type', 'Estimation_Accuracy', 'Est_Display', 'Spent_Display']
                    available_cols = [c for c in outlier_cols if c in est_outliers_display.columns]
                    
                    st.dataframe(
                        est_outliers_display[available_cols].head(15),
                        column_config={
                            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                            "Estimation_Accuracy": st.column_config.NumberColumn("Ratio", format="%.2f"),
                            "Est_Display": st.column_config.TextColumn("Estimated"),
                            "Spent_Display": st.column_config.TextColumn("Actual"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("ℹ️ No estimation data available. Tickets need 'Timeoriginalestimate' and 'Timespent' values.")
        
        st.divider()
    
    # =========================================================================
    # STANDOUT TICKETS ANALYSIS
    # =========================================================================
    if show_standout:
        st.header("🔍 Standout Tickets")
        st.caption("Identify tickets with extreme metrics values")
        
        # Metric descriptions and formulas
        METRIC_INFO = {
            "Cycle Time (Longest)": {
                "icon": "⏱️",
                "description": "Tickets that took the longest time from development start to completion. High cycle times may indicate blockers, complexity, or scope creep.",
                "formula": "Cycle Time = (Done/UAT/Resolved start) − (In Progress start)",
                "unit": "days",
                "insight": "Target: < 5 days for bugs, < 10 days for features"
            },
            "Cycle Time (Shortest)": {
                "icon": "⚡",
                "description": "Tickets completed fastest from development start. These represent ideal throughput and can help identify best practices.",
                "formula": "Cycle Time = (Done/UAT/Resolved start) − (In Progress start)",
                "unit": "days",
                "insight": "Quick wins and well-scoped tickets"
            },
            "Lead Time (Longest)": {
                "icon": "📏",
                "description": "Tickets with the longest total delivery time including planning and queue time. Highlights process inefficiencies from creation to completion.",
                "formula": "Lead Time = (Done/UAT/Resolved start) − (New/Created start)",
                "unit": "days",
                "insight": "Includes planning overhead + dev time"
            },
            "Lead Time (Shortest)": {
                "icon": "🚀",
                "description": "Tickets delivered fastest end-to-end. Represents optimal flow through the entire development pipeline.",
                "formula": "Lead Time = (Done/UAT/Resolved start) − (New/Created start)",
                "unit": "days",
                "insight": "Fast-tracked or urgent items"
            },
            "Flow Efficiency (Lowest)": {
                "icon": "🐢",
                "description": "Tickets with the most waiting time relative to active work. These spent too much time blocked or in queues.",
                "formula": "Flow Efficiency = (Active Time / (Active + Waiting Time)) × 100%",
                "unit": "%",
                "insight": "Active: In Progress, QA, UAT | Waiting: Blocked stages"
            },
            "Flow Efficiency (Highest)": {
                "icon": "🌊",
                "description": "Tickets with minimal waiting time—mostly active work. These moved efficiently through the pipeline.",
                "formula": "Flow Efficiency = (Active Time / (Active + Waiting Time)) × 100%",
                "unit": "%",
                "insight": "Target: > 40% is good, > 60% is excellent"
            },
            "Wait Time (Longest)": {
                "icon": "⏸️",
                "description": "Tickets that spent the most time waiting/blocked. Identifies bottlenecks and dependencies that slow delivery.",
                "formula": "Wait Time = Σ (time in waiting stages)",
                "unit": "days",
                "insight": "Waiting stages: Waiting on Eng, T2, Pending Unleash, etc."
            },
            "Handoff Delay (Longest)": {
                "icon": "🤝",
                "description": "Tickets with the longest delays during stage transitions. Exposes communication gaps and coordination issues between Dev and QA teams.",
                "formula": "Handoff Delay = (QA Ready start − In Progress end) + (QA start − QA Ready start)",
                "unit": "days",
                "insight": "Target: < 0.5 days (< 4 hours) per handoff"
            },
            "Handoff Delay (Shortest)": {
                "icon": "🔄",
                "description": "Tickets with the smoothest transitions between stages. These represent ideal handoff coordination.",
                "formula": "Handoff Delay = (QA Ready start − In Progress end) + (QA start − QA Ready start)",
                "unit": "days",
                "insight": "Best practices for seamless team transitions"
            },
            "Dev→QA Ready Delay": {
                "icon": "👨‍💻",
                "description": "Time between development completion and marking as QA ready. Long delays may indicate missing documentation, code review bottlenecks, or unclear handoff criteria.",
                "formula": "Delay = QA Ready start − (In Progress start + In Progress days)",
                "unit": "days",
                "insight": "Often caused by PR review backlog or unclear 'done' criteria"
            },
            "QA Ready→QA Delay": {
                "icon": "🧪",
                "description": "Time a ticket waits after being marked QA ready until testing actually begins. Identifies QA capacity constraints or prioritization issues.",
                "formula": "Delay = QA start − QA Ready start",
                "unit": "days",
                "insight": "Often caused by QA capacity or environment availability"
            },
            "Recurrence (Highest)": {
                "icon": "🔁",
                "description": "Tickets that bounced back the most times through QA, UAT, or rejection stages. Indicates unclear requirements, insufficient testing, or code quality issues.",
                "formula": "Total Recurrence = QA recurrence + UAT recurrence + Rejected recurrence",
                "unit": "count",
                "insight": "Target: < 5% overall recurrence rate"
            },
            "QA Recurrence (Highest)": {
                "icon": "🧪",
                "description": "Tickets that bounced back from QA most frequently. May indicate insufficient unit testing, unclear acceptance criteria, or environment issues.",
                "formula": "QA Recurrence = Stage QA recurrence count",
                "unit": "count",
                "insight": "Review test coverage and acceptance criteria"
            },
            "UAT Recurrence (Highest)": {
                "icon": "✅",
                "description": "Tickets that bounced back from UAT most frequently. Suggests misalignment between implementation and user expectations or business requirements.",
                "formula": "UAT Recurrence = Stage UAT recurrence count",
                "unit": "count",
                "insight": "Improve stakeholder communication and demos"
            },
            "Defect Escapes": {
                "icon": "🚨",
                "description": "Defects that passed QA but were caught later in UAT or Production. These represent gaps in test coverage or unclear acceptance criteria.",
                "formula": "Escape = (Reached UAT/Done) AND (Rejected/QA/In Progress recurrence > 0)",
                "unit": "boolean",
                "insight": "Target: < 5% escape rate. Review test strategy for patterns."
            },
            "Estimation (Most Underestimated)": {
                "icon": "📈",
                "description": "Tickets that took significantly longer than estimated. Indicates complexity was underestimated, scope creep, or blockers encountered.",
                "formula": "Estimation Accuracy = Timespent / Timeoriginalestimate",
                "unit": "ratio",
                "insight": ">1.2x = underestimated. Look for patterns in task types."
            },
            "Estimation (Most Overestimated)": {
                "icon": "📉",
                "description": "Tickets that finished much faster than estimated. May indicate padding estimates, improved skills, or simpler-than-expected work.",
                "formula": "Estimation Accuracy = Timespent / Timeoriginalestimate",
                "unit": "ratio",
                "insight": "<0.8x = overestimated. Team may be getting more efficient."
            },
        }
        
        # Configuration
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            metric_choice = st.selectbox(
                "Select Metric",
                options=list(METRIC_INFO.keys()),
                index=0,
                help="Choose which metric to rank tickets by. Hover over the info box below for details."
            )
        
        with col2:
            top_n = st.slider("Number of Tickets", min_value=5, max_value=25, value=10)
        
        with col3:
            show_chart = st.toggle("Show Chart", value=True)
        
        # Display metric info box
        metric_info = METRIC_INFO[metric_choice]
        with st.container():
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                    border-left: 4px solid #667eea;
                    padding: 16px 20px;
                    border-radius: 8px;
                    margin: 10px 0 20px 0;
                ">
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 1.5em; margin-right: 10px;">{metric_info['icon']}</span>
                        <strong style="color: #e2e8f0; font-size: 1.1em;">{metric_choice}</strong>
                    </div>
                    <p style="color: #cbd5e1; margin: 8px 0; font-size: 0.95em;">
                        {metric_info['description']}
                    </p>
                    <div style="
                        background: rgba(102, 126, 234, 0.15);
                        padding: 10px 14px;
                        border-radius: 6px;
                        margin-top: 12px;
                        font-family: 'SF Mono', 'Fira Code', monospace;
                    ">
                        <span style="color: #94a3b8; font-size: 0.8em;">Formula:</span>
                        <code style="color: #a5b4fc; font-size: 0.9em; display: block; margin-top: 4px;">
                            {metric_info['formula']}
                        </code>
                    </div>
                    <p style="color: #64748b; font-size: 0.85em; margin: 10px 0 0 0; font-style: italic;">
                        💡 {metric_info['insight']}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # Prepare data based on selection
        chart_data = None
        chart_title = ""
        chart_color = "#667eea"
        
        if "Cycle Time" in metric_choice:
            valid_df = df_active[df_active['Cycle_Time'].notna()].copy()
            if len(valid_df) > 0:
                ascending = "Shortest" in metric_choice
                valid_df = valid_df.sort_values('Cycle_Time', ascending=ascending).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Cycle_Time', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Cycle_Time']
                chart_title = f"{'Shortest' if ascending else 'Longest'} Cycle Time"
                chart_color = "#22c55e" if ascending else "#ef4444"
        
        elif "Lead Time" in metric_choice:
            valid_df = df_active[df_active['Lead_Time'].notna()].copy()
            if len(valid_df) > 0:
                ascending = "Shortest" in metric_choice
                valid_df = valid_df.sort_values('Lead_Time', ascending=ascending).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Lead_Time', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Lead_Time']
                chart_title = f"{'Shortest' if ascending else 'Longest'} Lead Time"
                chart_color = "#22c55e" if ascending else "#ef4444"
        
        elif "Flow Efficiency" in metric_choice:
            valid_df = df_active[df_active['Flow_Efficiency'].notna()].copy()
            if len(valid_df) > 0:
                ascending = "Lowest" in metric_choice
                valid_df = valid_df.sort_values('Flow_Efficiency', ascending=ascending).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Flow_Efficiency', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Flow_Efficiency']
                chart_title = f"{'Lowest' if ascending else 'Highest'} Flow Efficiency"
                chart_color = "#ef4444" if ascending else "#22c55e"
        
        elif "Wait Time" in metric_choice:
            valid_df = df_active[df_active['Waiting_Time_Total'].notna()].copy()
            if len(valid_df) > 0:
                valid_df = valid_df.sort_values('Waiting_Time_Total', ascending=False).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Waiting_Time_Total', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Waiting_Time_Total']
                chart_title = "Longest Wait Time"
                chart_color = "#ef4444"
        
        elif "Handoff Delay" in metric_choice:
            valid_df = df_active[df_active['Handoff_Total'].notna()].copy()
            valid_df = valid_df[valid_df['Handoff_Total'] > 0]
            if len(valid_df) > 0:
                ascending = "Shortest" in metric_choice
                valid_df = valid_df.sort_values('Handoff_Total', ascending=ascending).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Handoff_Total', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Handoff_Total']
                chart_title = f"{'Shortest' if ascending else 'Longest'} Handoff Delay"
                chart_color = "#22c55e" if ascending else "#ef4444"
        
        elif "Dev→QA Ready" in metric_choice:
            valid_df = df_active[df_active['Handoff_Dev_QA_Ready'].notna()].copy()
            valid_df = valid_df[valid_df['Handoff_Dev_QA_Ready'] > 0]
            if len(valid_df) > 0:
                valid_df = valid_df.sort_values('Handoff_Dev_QA_Ready', ascending=False).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Handoff_Dev_QA_Ready', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Handoff_Dev_QA_Ready']
                chart_title = "Longest Dev → QA Ready Delay"
                chart_color = "#ef4444"
        
        elif "QA Ready→QA" in metric_choice:
            valid_df = df_active[df_active['Handoff_QA_Ready_QA'].notna()].copy()
            valid_df = valid_df[valid_df['Handoff_QA_Ready_QA'] > 0]
            if len(valid_df) > 0:
                valid_df = valid_df.sort_values('Handoff_QA_Ready_QA', ascending=False).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Handoff_QA_Ready_QA', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Handoff_QA_Ready_QA']
                chart_title = "Longest QA Ready → QA Delay"
                chart_color = "#ef4444"
        
        elif "Recurrence (Highest)" in metric_choice:
            valid_df = df_active[df_active['Total_Recurrence'].notna()].copy()
            valid_df = valid_df[valid_df['Total_Recurrence'] > 0]
            if len(valid_df) > 0:
                valid_df = valid_df.sort_values('Total_Recurrence', ascending=False).head(top_n)
                chart_data = valid_df[['ID', 'Name', 'Total_Recurrence', 'Type']].copy()
                chart_data['Metric_Value'] = chart_data['Total_Recurrence']
                chart_title = "Highest Total Recurrence"
                chart_color = "#ef4444"
        
        elif "QA Recurrence" in metric_choice:
            col_name = 'Stage QA recurrence'
            if col_name in df_active.columns:
                df_active['_qa_rec'] = pd.to_numeric(df_active[col_name], errors='coerce').fillna(0)
                valid_df = df_active[df_active['_qa_rec'] > 0].copy()
                if len(valid_df) > 0:
                    valid_df = valid_df.sort_values('_qa_rec', ascending=False).head(top_n)
                    chart_data = valid_df[['ID', 'Name', '_qa_rec', 'Type']].copy()
                    chart_data['Metric_Value'] = chart_data['_qa_rec']
                    chart_title = "Highest QA Recurrence"
                    chart_color = "#ef4444"
        
        elif "UAT Recurrence" in metric_choice:
            col_name = 'Stage UAT recurrence'
            if col_name in df_active.columns:
                df_active['_uat_rec'] = pd.to_numeric(df_active[col_name], errors='coerce').fillna(0)
                valid_df = df_active[df_active['_uat_rec'] > 0].copy()
                if len(valid_df) > 0:
                    valid_df = valid_df.sort_values('_uat_rec', ascending=False).head(top_n)
                    chart_data = valid_df[['ID', 'Name', '_uat_rec', 'Type']].copy()
                    chart_data['Metric_Value'] = chart_data['_uat_rec']
                    chart_title = "Highest UAT Recurrence"
                    chart_color = "#ef4444"
        
        elif "Defect Escapes" in metric_choice:
            # Show escaped defects (tickets that passed QA but were sent back from UAT+)
            if 'Is_Escape' in df_active.columns:
                valid_df = df_active[df_active['Is_Escape'] == True].copy()
                if len(valid_df) > 0:
                    # Calculate a "severity" score for sorting (sum of bounce counts)
                    severity = pd.Series([0.0] * len(valid_df), index=valid_df.index)
                    for col in ['Stage Rejected recurrence', 'Stage QA recurrence', 'Stage In Progress recurrence']:
                        if col in valid_df.columns:
                            # Subtract 1 because recurrence=1 is first entry, not a bounce
                            severity += (pd.to_numeric(valid_df[col], errors='coerce').fillna(0) - 1).clip(lower=0)
                    valid_df['_escape_severity'] = severity
                    valid_df = valid_df.sort_values('_escape_severity', ascending=False).head(top_n)
                    chart_data = valid_df[['ID', 'Name', '_escape_severity', 'Type']].copy()
                    chart_data['Metric_Value'] = chart_data['_escape_severity']
                    chart_title = "Defect Escapes (by bounce count)"
                    chart_color = "#ef4444"
        
        elif "Estimation" in metric_choice:
            if 'Estimation_Accuracy' in df_active.columns:
                valid_df = df_active[df_active['Estimation_Accuracy'].notna()].copy()
                valid_df = valid_df[valid_df['Estimation_Accuracy'] > 0]
                if len(valid_df) > 0:
                    if "Underestimated" in metric_choice:
                        # Sort descending - highest ratio = most underestimated
                        valid_df = valid_df.sort_values('Estimation_Accuracy', ascending=False).head(top_n)
                        chart_title = "Most Underestimated (took longer)"
                        chart_color = "#ef4444"
                    else:
                        # Overestimated - sort ascending - lowest ratio = most overestimated
                        valid_df = valid_df.sort_values('Estimation_Accuracy', ascending=True).head(top_n)
                        chart_title = "Most Overestimated (finished faster)"
                        chart_color = "#22c55e"
                    
                    chart_data = valid_df[['ID', 'Name', 'Estimation_Accuracy', 'Type']].copy()
                    chart_data['Metric_Value'] = chart_data['Estimation_Accuracy']
        
        if chart_data is not None and len(chart_data) > 0:
            # Show bar chart
            if show_chart:
                import plotly.express as px
                
                # Truncate names for display
                chart_data['Display_Name'] = chart_data['ID'] + ': ' + chart_data['Name'].str[:30] + '...'
                
                fig = px.bar(
                    chart_data,
                    x='Metric_Value',
                    y='Display_Name',
                    orientation='h',
                    title=f"Top {len(chart_data)} Tickets - {chart_title}",
                    color_discrete_sequence=[chart_color],
                    hover_data={'ID': True, 'Name': True, 'Type': True, 'Metric_Value': ':.1f'}
                )
                fig.update_layout(
                    yaxis={'categoryorder': 'total ascending' if 'Longest' in metric_choice or 'Lowest' in metric_choice else 'total descending'},
                    xaxis_title="Days" if "Efficiency" not in metric_choice else "Efficiency %",
                    yaxis_title="",
                    height=max(300, top_n * 35),
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Show data table
            with st.expander(f"📋 View {len(chart_data)} Tickets Data"):
                display_cols = ['ID', 'Name', 'Type', 'Metric_Value']
                if 'Link' in df_active.columns:
                    chart_data['Link'] = df_active.loc[chart_data.index, 'Link'].values
                    display_cols = ['ID', 'Link', 'Name', 'Type', 'Metric_Value']
                
                metric_label = "Cycle Time (days)" if "Cycle" in metric_choice else \
                              "Lead Time (days)" if "Lead" in metric_choice else \
                              "Flow Efficiency %" if "Efficiency" in metric_choice else \
                              "Handoff Delay (days)" if "Handoff" in metric_choice or "→" in metric_choice else \
                              "Recurrence Count" if "Recurrence" in metric_choice else \
                              "Escape Severity" if "Escape" in metric_choice else \
                              "Estimation Ratio" if "Estimation" in metric_choice else \
                              "Wait Time (days)"
                
                st.dataframe(
                    chart_data[display_cols],
                    column_config={
                        "ID": st.column_config.TextColumn("ID"),
                        "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                        "Name": st.column_config.TextColumn("Name", width="large"),
                        "Type": st.column_config.TextColumn("Type"),
                        "Metric_Value": st.column_config.NumberColumn(metric_label, format="%.1f"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info("ℹ️ No data available for the selected metric.")
        
        st.divider()
    
    # Download cleaned CSV (only active tickets)
    st.subheader("📥 Download Filtered Data")
    st.caption(f"Contains {len(df_active)} tickets based on current filter settings")
    
    export_df = df_active.drop(columns=['_sp', '_completed'], errors='ignore')
    st.download_button(
        label=f"⬇️ Download Filtered CSV ({len(df_active)} rows)",
        data=export_df.to_csv(index=False, sep=';'),
        file_name=f"iapts_{st.session_state.current_sprint}_filtered.csv",
        mime="text/csv",
        type="primary"
    )


if __name__ == "__main__":
    main()
