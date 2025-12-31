# DORA Metrics Dashboard - Streamlit App

Interactive dashboard for analyzing engineering metrics from Jira data.

## Features

📊 **DORA Metrics**
- Lead Time for Changes (with performance rating)
- Deployment Frequency
- Change Failure Rate
- Mean Time to Recovery (MTTR)

⏱️ **Cycle Time Analysis**
- Stacked bar chart by stage and issue type
- Lead time distribution histogram
- Percentile markers (Average, 90th percentile)

💰 **Investment Allocation**
- Pie chart by issue type
- Bar chart by component/labels

📈 **Velocity & Throughput**
- Weekly throughput trend with trendline
- Monthly throughput by type (area chart)

🔄 **Backtrack Analysis**
- Backtrack count and rate
- Backtracks by stage

## Installation

```bash
cd streamlit_app
pip install -r requirements.txt
```

## Running the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage

1. Upload your Jira CSV file (exported using the jira-lead-cycle-time-duration-extractor)
2. Use sidebar filters to narrow down by issue type or date range
3. Explore the metrics and charts
4. Download processed data with calculated metrics

## CSV Format

The app expects a CSV with these column patterns:
- `ID` - Issue key (e.g., PROJ-123)
- `Type` - Issue type (Story, Bug, Task, etc.)
- `Stage X days` - Duration in days for each stage
- `Stage X start` - Start date for each stage
- `Stage X recurrence` - How many times issue entered this stage

## Screenshots

### DORA Metrics Overview
Shows the four key DORA metrics with performance ratings (Elite/High/Medium/Low)

### Cycle Time Analysis
- Stacked bar chart showing median time in each stage
- Histogram showing lead time distribution

### Investment Allocation
- Pie chart of issues by type
- Bar chart of top components/labels

### Velocity Trend
- Line chart showing weekly throughput
- Area chart showing monthly breakdown by type


