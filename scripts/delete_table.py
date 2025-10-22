#!/usr/bin/env python3
import sys
import yaml
import subprocess

def main():
    try:
        yaml_content = sys.stdin.read()
        data = yaml.safe_load(yaml_content)

        if not data:
            print("YAML content is empty.")
            sys.exit(1)

        table_bucket_arn = data.get("tableBucketARN")
        namespace = data.get("namespace")
        name = data.get("name")

        if not table_bucket_arn or not namespace or not name:
            print("Missing required fields in YAML (expected: tableBucketARN, namespace, name).")
            sys.exit(1)

        cmd = [
            "aws", "s3tables", "delete-table",
            "--table-bucket-arn", table_bucket_arn,
            "--namespace", namespace,
            "--name", name
        ]

        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Successfully deleted S3 table: {namespace}.{name}")
        else:
            print(f"❌ Failed to delete table {namespace}.{name}")
            print(result.stderr)
            sys.exit(result.returncode)

    except yaml.YAMLError as e:
        print(f"YAML parsing error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
