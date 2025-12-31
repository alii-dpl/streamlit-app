import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from metrics import (
    load_jira_csv,
    calculate_lead_time,
    calculate_cycle_time,
    calculate_done_date,
    calculate_backtracks,
    lead_time_average,
    lead_time_median,
    lead_time_percentile_90,
    cycle_time_average,
    cycle_time_median,
    cycle_time_percentile_90,
    deployment_frequency,
    change_failure_rate,
    mean_time_to_recovery,
    total_backtracks,
    backtrack_rate,
    backtracks_by_stage,
    throughput_completed,
    weekly_throughput,
    monthly_throughput,
    cycle_time_by_stage_and_type,
    issues_by_type,
    issues_by_component,
    issues_by_assignee,
    get_dora_rating,
    has_story_points,
    story_points_total,
    story_points_completed,
    story_points_average,
    story_points_by_type,
    story_points_by_assignee,
    velocity_weekly,
    lead_time_per_story_point
)

# Formulas for tooltips
# Obsolete/Duplicate tickets are excluded from all calculations
# Done = has "Stage UAT start" OR "Stage Done start"
FORMULAS = {
    'lead_time': 'Lead Time = MAX(Stage start dates) - MIN(Stage start dates)',
    'deploy_freq': 'Deployment Frequency = Completed Issues / Date Range (days)',
    'cfr': 'Change Failure Rate = (Bug Count / Total Issues) × 100',
    'mttr': 'MTTR = Average Lead Time for issues where Type = "Bug"',
    'cycle_time_median': 'Median Cycle Time = MEDIAN(SUM of all "Stage * days" columns)',
    'cycle_time_avg': 'Average Cycle Time = AVERAGE(SUM of all "Stage * days" columns)',
    'cycle_time_p90': '90th Percentile = PERCENTILE(Cycle Time, 0.90)',
    'completed': 'Completed = has "Stage UAT start" OR "Stage Done start"',
    'backtracks_total': 'Total Backtracks = SUM of stages where recurrence > 1',
    'backtrack_rate': 'Backtrack Rate = (Issues with Backtracks / Total Issues) × 100',
    'backtrack_issues': 'Issues with Backtracks = COUNT where any stage recurrence > 1',
    'sp_total': 'Total Story Points = SUM(StoryPoints)',
    'sp_completed': 'Completed SP = SUM(StoryPoints) where issue is Done',
    'sp_avg': 'Average SP = AVERAGE(StoryPoints) for issues with points > 0',
    'sp_velocity': 'Velocity = Story Points completed per week',
    'sp_efficiency': 'Efficiency = Lead Time (days) / Story Point'
}

st.set_page_config(page_title="DORA Metrics Dashboard", page_icon="📊", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        padding: 15px 20px;
        border-radius: 12px;
    }
    div[data-testid="stMetric"] label { color: #e0e0e0 !important; }
    div[data-testid="stMetricValue"] { color: white !important; font-size: 1.8rem; }
</style>
""", unsafe_allow_html=True)


def main():
    st.title("📊 DORA Metrics Dashboard")
    
    with st.sidebar:
        st.header("📁 Upload Data")
        uploaded_file = st.file_uploader("Upload Jira CSV", type=['csv'])
    
    if not uploaded_file:
        st.info("👆 Upload your Jira CSV file to get started")
        return
    
    # Load CSV and filter obsolete/duplicate tickets immediately
    df, total_raw, obsolete_count = load_jira_csv(uploaded_file)
    
    # Debug: Verify filtering worked
    print(f"\n=== APP.PY DEBUG ===")
    print(f"  Total raw: {total_raw}")
    print(f"  Obsolete removed: {obsolete_count}")
    print(f"  Active (df rows): {len(df)}")
    
    df['Lead_Time'] = calculate_lead_time(df)
    df['Cycle_Time'] = calculate_cycle_time(df)
    df['Done_Date'] = calculate_done_date(df)
    df['Backtracks'] = calculate_backtracks(df)
    
    # Show filter info - always show to confirm filtering
    st.success(f"📋 **{total_raw}** total issues → removed **{obsolete_count}** obsolete/duplicate → **{len(df)}** active issues")
    
    with st.sidebar:
        st.header("🎛️ Filters")
        
        if 'Type' in df.columns:
            types = df['Type'].dropna().unique().tolist()
            selected_types = st.multiselect("Type", types, default=types)
            df = df[df['Type'].isin(selected_types)]
        
        valid_dates = df['Done_Date'].dropna()
        if len(valid_dates) > 0:
            min_date, max_date = valid_dates.min(), valid_dates.max()
            date_range = st.date_input("Date Range", value=(min_date, max_date))
            if len(date_range) == 2:
                df = df[(df['Done_Date'] >= pd.Timestamp(date_range[0])) & 
                        (df['Done_Date'] <= pd.Timestamp(date_range[1]))]
        
        st.divider()
        st.header("📥 Export")
        st.caption(f"**{len(df)}** issues (obsolete/duplicate removed)")
        
        # Download filtered CSV - explicitly create from current df
        filtered_csv = df.to_csv(index=False, sep=';')
        print(f"  Download CSV rows: {len(df)}")  # Debug
        st.download_button(
            label=f"⬇️ Download ({len(df)} rows)",
            data=filtered_csv,
            file_name="filtered_jira_data.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # DORA Metrics
    st.header("🚀 DORA Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    lt_avg = lead_time_average(df)
    rating, color = get_dora_rating('lead_time', lt_avg)
    with col1:
        st.metric("Lead Time (Avg)", f"{lt_avg:.1f} days", help=FORMULAS['lead_time'])
        st.markdown(f"<span style='background:{color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold'>{rating}</span>", unsafe_allow_html=True)
    
    deploy_freq = deployment_frequency(df)
    rating, color = get_dora_rating('deploy_freq', deploy_freq)
    with col2:
        st.metric("Deployment Frequency", f"{deploy_freq:.2f}/day", help=FORMULAS['deploy_freq'])
        st.markdown(f"<span style='background:{color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold'>{rating}</span>", unsafe_allow_html=True)
    
    cfr = change_failure_rate(df)
    rating, color = get_dora_rating('change_failure_rate', cfr)
    with col3:
        st.metric("Change Failure Rate", f"{cfr:.1f}%", help=FORMULAS['cfr'])
        st.markdown(f"<span style='background:{color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold'>{rating}</span>", unsafe_allow_html=True)
    
    mttr = mean_time_to_recovery(df)
    rating, color = get_dora_rating('mttr', mttr)
    with col4:
        st.metric("MTTR", f"{mttr:.1f} days", help=FORMULAS['mttr'])
        st.markdown(f"<span style='background:{color};color:white;padding:4px 12px;border-radius:20px;font-weight:bold'>{rating}</span>", unsafe_allow_html=True)
    
    st.divider()
    
    # Cycle Time Analysis
    st.header("⏱️ Cycle Time Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        stage_data = cycle_time_by_stage_and_type(df)
        if len(stage_data) > 0:
            stage_cols_chart = [c for c in stage_data.columns if c != 'Type' and stage_data[c].sum() > 0]
            if stage_cols_chart:
                fig = px.bar(stage_data, x='Type', y=stage_cols_chart, 
                            title="Median Cycle Time by Stage", barmode='stack',
                            color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(yaxis_title="Days", legend_title="Stage")
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        lead_times = pd.to_numeric(df['Lead_Time'], errors='coerce').dropna()
        if len(lead_times) > 0:
            fig = px.histogram(lead_times, nbins=20, title="Lead Time Distribution",
                              color_discrete_sequence=['#667eea'])
            fig.add_vline(x=lead_times.mean(), line_dash="dash", line_color="green",
                         annotation_text=f"Avg: {lead_times.mean():.1f}d")
            fig.add_vline(x=lead_times.quantile(0.9), line_dash="dash", line_color="red",
                         annotation_text=f"90th: {lead_times.quantile(0.9):.1f}d")
            st.plotly_chart(fig, use_container_width=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Median Cycle Time", f"{cycle_time_median(df):.1f} days", help=FORMULAS['cycle_time_median'])
    with col2:
        st.metric("Average Cycle Time", f"{cycle_time_average(df):.1f} days", help=FORMULAS['cycle_time_avg'])
    with col3:
        st.metric("90th Percentile", f"{cycle_time_percentile_90(df):.1f} days", help=FORMULAS['cycle_time_p90'])
    with col4:
        st.metric("Completed Issues", f"{throughput_completed(df)}", help=FORMULAS['completed'])
    
    st.divider()
    
    # Investment Allocation
    st.header("💰 Investment Allocation")
    col1, col2 = st.columns(2)
    
    with col1:
        type_counts = issues_by_type(df)
        if len(type_counts) > 0:
            fig = px.pie(values=type_counts.values, names=type_counts.index,
                        title="Issues by Type", color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        comp_counts = issues_by_component(df)
        if len(comp_counts) > 0:
            fig = px.bar(x=comp_counts.values, y=comp_counts.index, orientation='h',
                        title="Top 10 Components", color=comp_counts.values,
                        color_continuous_scale='Viridis')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No Components data available")
    
    st.divider()
    
    # Story Points (only show if data available)
    if has_story_points(df):
        st.header("🎯 Story Points & Velocity")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Story Points", f"{story_points_total(df):.0f}", help=FORMULAS['sp_total'])
        with col2:
            st.metric("Completed SP", f"{story_points_completed(df):.0f}", help=FORMULAS['sp_completed'])
        with col3:
            st.metric("Avg SP/Issue", f"{story_points_average(df):.1f}", help=FORMULAS['sp_avg'])
        with col4:
            st.metric("Days/Story Point", f"{lead_time_per_story_point(df):.1f}", help=FORMULAS['sp_efficiency'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            sp_by_type = story_points_by_type(df)
            if len(sp_by_type) > 0:
                fig = px.pie(values=sp_by_type.values, names=sp_by_type.index,
                            title="Story Points by Type", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_traces(textposition='inside', textinfo='percent+value')
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            velocity = velocity_weekly(df)
            if len(velocity) > 0:
                fig = px.bar(velocity, x='Week', y='StoryPoints', title="Weekly Velocity (Story Points)",
                            color='StoryPoints', color_continuous_scale='Greens')
                avg_velocity = velocity['StoryPoints'].mean()
                fig.add_hline(y=avg_velocity, line_dash="dash", line_color="red",
                             annotation_text=f"Avg: {avg_velocity:.1f}")
                st.plotly_chart(fig, use_container_width=True)
        
        sp_by_assignee = story_points_by_assignee(df)
        if len(sp_by_assignee) > 0:
            fig = px.bar(x=sp_by_assignee.index, y=sp_by_assignee.values,
                        title="Story Points by Assignee (Top 10)", color=sp_by_assignee.values,
                        color_continuous_scale='Purples')
            fig.update_layout(showlegend=False, xaxis_title="Assignee", yaxis_title="Story Points")
            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
    
    # Velocity & Throughput
    st.header("📈 Velocity & Throughput")
    col1, col2 = st.columns(2)
    
    with col1:
        weekly = weekly_throughput(df)
        if len(weekly) > 0:
            fig = px.line(weekly, x='Week', y='Count', title="Weekly Throughput (Issues reaching UAT)",
                         markers=True, color_discrete_sequence=['#667eea'])
            if len(weekly) > 2:
                z = np.polyfit(weekly['Week'], weekly['Count'], 1)
                p = np.poly1d(z)
                fig.add_trace(go.Scatter(x=weekly['Week'], y=p(weekly['Week']),
                                        mode='lines', name='Trend',
                                        line=dict(dash='dash', color='red')))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        monthly = monthly_throughput(df)
        if len(monthly) > 0:
            fig = px.area(monthly, title="Monthly Throughput by Type",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Backtrack Analysis
    st.header("🔄 Backtrack Analysis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Backtracks", f"{total_backtracks(df)}", help=FORMULAS['backtracks_total'])
    with col2:
        st.metric("Backtrack Rate", f"{backtrack_rate(df):.1f}%", help=FORMULAS['backtrack_rate'])
    with col3:
        st.metric("Issues with Backtracks", f"{(df['Backtracks'] > 0).sum()}", help=FORMULAS['backtrack_issues'])
    
    bt_df = backtracks_by_stage(df)
    if len(bt_df) > 0:
        fig = px.bar(bt_df, x='Backtracks', y='Stage', orientation='h',
                    title="Backtracks by Stage", color='Backtracks', color_continuous_scale='Reds')
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Team Performance
    st.header("👥 Team Performance")
    assignee_counts = issues_by_assignee(df)
    if len(assignee_counts) > 0:
        fig = px.bar(x=assignee_counts.index, y=assignee_counts.values,
                    title="Issues by Assignee (Top 10)", color=assignee_counts.values,
                    color_continuous_scale='Blues')
        fig.update_layout(showlegend=False, xaxis_title="Assignee", yaxis_title="Issues")
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Data Explorer
    st.header("📋 Data Explorer")
    display_cols = ['ID', 'Name', 'Type', 'StoryPoints', 'Lead_Time', 'Cycle_Time', 'Backtracks', 'Stage', 'StatusCategory', 'AssigneeName']
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols].head(100), use_container_width=True, hide_index=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Download Filtered CSV (semicolon)", 
            df.to_csv(index=False, sep=';'), 
            "filtered_jira_data.csv", 
            "text/csv",
            use_container_width=True
        )
    with col2:
        st.download_button(
            "📥 Download Filtered CSV (comma)", 
            df.to_csv(index=False), 
            "filtered_jira_data_comma.csv", 
            "text/csv",
            use_container_width=True
        )


if __name__ == "__main__":
    main()
