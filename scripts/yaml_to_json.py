#!/usr/bin/env python3
"""
Convert YAML file to JSON format for AWS CLI.
Usage: python yaml_to_json.py <yaml_file_path> <output_json_path>
"""

import yaml
import json
import sys

def yaml_to_json(yaml_file, json_file):
    """Convert YAML file to JSON."""
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)

        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Successfully converted {yaml_file} to {json_file}")

    except FileNotFoundError:
        print(f"ERROR: File not found: {yaml_file}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python yaml_to_json.py <yaml_file_path> <output_json_path>", file=sys.stderr)
        sys.exit(1)

    yaml_file = sys.argv[1]
    json_file = sys.argv[2]
    yaml_to_json(yaml_file, json_file)