#!/usr/bin/env python3
"""
Parse S3 table definition YAML and extract table details.
Usage: python parse_table.py <yaml_file_path>
Output: tableBucketARN|namespace|name
"""

import yaml
import sys


def parse_table_definition(file_path):
    """Parse YAML file and extract table details."""
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        table_bucket_arn = data.get('tableBucketARN', '')
        namespace = data.get('namespace', '')
        name = data.get('name', '')

        if not all([table_bucket_arn, namespace, name]):
            print("ERROR: Missing required fields (tableBucketARN, namespace, or name)", file=sys.stderr)
            sys.exit(1)

        # Output in pipe-delimited format for easy parsing in bash
        print(f'{table_bucket_arn}|{namespace}|{name}')

    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_table.py <yaml_file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    parse_table_definition(file_path)
