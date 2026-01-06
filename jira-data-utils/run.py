#!/usr/bin/env python3
"""
Run script - Execute Jira data extraction using config.yaml

Usage:
    python run.py [config_path]
    
If no config path is provided, looks for config.yaml in the parent directory.
"""
import sys
import os
from pathlib import Path

# Add package directory to path
pkg_dir = Path(__file__).parent
sys.path.insert(0, str(pkg_dir))

from extractor import JiraExtractor
from components.yaml_converter import load_yaml_config, convert_yaml_to_jira_settings


def main(config_path: str = None):
    """
    Main entry point for extraction
    
    Args:
        config_path: Path to config.yaml file
    """
    # Default config path
    if config_path is None:
        # Look in parent directory (jira-lead-cycle-time-duration-extractor)
        config_path = pkg_dir.parent / 'jira-lead-cycle-time-duration-extractor' / 'config.yaml'
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        print("Please provide a valid config.yaml path")
        sys.exit(1)
    
    print(f"Loading config from: {config_path}")
    
    # Load and convert config
    yaml_config = load_yaml_config(str(config_path))
    config = convert_yaml_to_jira_settings(yaml_config)
    
    print(f"JQL Query: {config.custom_jql}")
    print(f"Jira URL: {config.connection.url}")
    
    # Create extractor and run
    extractor = JiraExtractor(config)
    
    def progress_hook(percent: int):
        print(f"Progress: {percent}%")
    
    # Extract all issues
    work_items = extractor.extract_all(status_hook=progress_hook, debug=True)
    
    # Convert to CSV
    csv_content = extractor.to_csv(work_items)
    
    # Determine output file
    output_file = config.output_file
    if not output_file:
        output_file = f"output_{int(os.times().elapsed * 1000)}.csv"
    
    # Make output path relative to config directory
    output_path = config_path.parent / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write CSV
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    print(f"\n✅ Extraction complete!")
    print(f"   Issues extracted: {len(work_items)}")
    print(f"   Output file: {output_path}")


if __name__ == '__main__':
    config_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(config_arg)
