# S3 Tables Automation

Automate AWS S3 Iceberg table creation and deletion using GitLab CI/CD.

## 🚀 How It Works

1. Add/modify YAML files in `table-definitions/` folder
2. Commit and push to GitLab
3. GitLab runner automatically creates S3 tables
4. Delete YAML files to automatically delete S3 tables

## 📁 Project Structure
```
s3table_automation/
├── .gitlab-ci.yml          # GitLab CI/CD pipeline
├── README.md
├── scripts/
│   ├── parse_table.py      # Parse YAML table definitions
│   └── yaml_to_json.py     # Convert YAML to JSON
└── table-definitions/
    └── example_table.yaml  # Table definition
```

## ⚙️ Setup

### 1. Configure GitLab CI/CD Variables

Go to **Settings → CI/CD → Variables** and add:

- `AWS_ACCESS_KEY_ID` (masked, protected)
- `AWS_SECRET_ACCESS_KEY` (masked, protected)

### 2. Enable Shared Runners

Go to **Settings → CI/CD → Runners** and enable instance runners.

### 3. Create Table Definitions

Add YAML files to `table-definitions/` folder:
```yaml
tableBucketARN: "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket"
namespace: "my_namespace"
name: "my_table"
format: "ICEBERG"
metadata:
  iceberg:
    schema:
      fields:
        - name: "id"
          type: "int"
          required: true
        - name: "name"
          type: "string"
```

### 4. Push to GitLab
```bash
git add table-definitions/my_table.yaml
git commit -m "Add new table definition"
git push
```

## 🗑️ Delete Tables

Simply delete the YAML file:
```bash
git rm table-definitions/my_table.yaml
git commit -m "Delete my_table"
git push
```

The pipeline will automatically delete the S3 table.

## 🧪 Test Locally
```bash
# Test parse_table.py
python3 scripts/parse_table.py table-definitions/example_table.yaml

# Test yaml_to_json.py
python3 scripts/yaml_to_json.py table-definitions/example_table.yaml output.json
```

## 📝 Pipeline Stages

1. **delete-tables** - Deletes S3 tables for removed YAML files
2. **create-tables** - Creates S3 tables from new/modified YAML files

## 🔐 IAM Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3tables:CreateTable",
        "s3tables:DeleteTable"
      ],
      "Resource": "*"
    }
  ]
}
```