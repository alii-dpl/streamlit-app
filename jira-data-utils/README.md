# Jira Data Python

Python version of the Jira Lead/Cycle Time Duration Extractor. This package extracts Jira issues and calculates stage durations for lead time, cycle time, and DORA metrics analysis.

## Structure

```
jira-data-python/
├── __init__.py              # Package init
├── jira_types.py            # Type definitions (dataclasses)
├── extractor.py             # Main JiraExtractor class
├── run.py                   # Standalone run script
├── requirements.txt         # Dependencies
├── components/
│   ├── __init__.py
│   ├── jira_adapter.py      # HTTP requests to Jira API
│   ├── query_builder.py     # Build Jira API URLs
│   ├── fields_parser.py     # Parse nested field attributes
│   ├── staging_parser.py    # Parse changelog & calculate durations
│   ├── yaml_converter.py    # Load/convert YAML config
│   └── jira_work_item.py    # Work item class
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Standalone Run

```bash
# Uses config.yaml from jira-lead-cycle-time-duration-extractor
python run.py

# Or specify a config file
python run.py /path/to/config.yaml
```

### As a Module (for Streamlit integration)

```python
from jira_data_python import (
    JiraExtractor,
    load_yaml_config,
    convert_yaml_to_jira_settings,
)

# Load config
yaml_config = load_yaml_config('config.yaml')
config = convert_yaml_to_jira_settings(yaml_config)

# Create extractor
extractor = JiraExtractor(config)

# Extract issues
work_items = extractor.extract_all()

# Convert to CSV
csv_content = extractor.to_csv(work_items)
```

### Programmatic Configuration

```python
from jira_data_python import (
    JiraExtractor,
    JiraExtractorConfig,
    Auth,
    ConnectionConfig,
)

config = JiraExtractorConfig(
    connection=ConnectionConfig(
        url='https://your-company.atlassian.net/',
        auth=Auth(
            username='your-email@company.com',
            password='your-api-token'
        )
    ),
    custom_jql='project = "MYPROJECT" AND Sprint = "Sprint 1"',
    attributes={
        'Stage': 'status.name',
        'StoryPoints': 'customfield_10024',
        # ... more attributes
    }
)

extractor = JiraExtractor(config)
work_items = extractor.extract_all()
```

## Config YAML Format

The config.yaml format matches the Node.js version:

```yaml
Connection:
    Domain: https://your-company.atlassian.net/
    Username: your-email@company.com
    Password: your-api-token

JQL: 
    Query: project = "MYPROJECT" AND Sprint = "Sprint 1"

OutPutFileName: results/output.csv

Attributes:
    Stage: status.name
    StatusCategory: status.statusCategory.name
    Level: priority.name
    Labels: labels
    Components: components.name
    StoryPoints: customfield_10024
    # ... more attributes
```

## Output

The extractor produces a CSV with:
- **ID**: Jira issue key
- **Link**: URL to the issue
- **Name**: Issue summary
- **Type**: Issue type (Story, Bug, etc.)
- **Stage X days**: Time spent in each stage (days)
- **Stage X start**: When the issue entered each stage
- **Stage X recurrence**: How many times the issue entered each stage
- **Attributes**: Custom fields you configured

