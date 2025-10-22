# S3 Tables Automation

Automate and govern your AWS S3 Iceberg tables using GitLab CI/CD. Define tables via YAML—when a YAML file is added or updated, it gets reviewed, merged, and automatically provisions an Iceberg table with its schema. Delete the YAML and push changes? The corresponding table is automatically removed. Fully automated, central, and auditable process for managing S3 tables.  

[Video Demo & Code](https://lnkd.in/eDVB_kM9)  

## 🚀 How It Works

1. Add or modify YAML files in the `table-definitions/` folder  
2. Commit and push to GitLab  
3. GitLab runner automatically creates Iceberg S3 tables  
4. Delete YAML files to automatically delete corresponding S3 tables  

## 📁 Project Structure
```
├── README.md
├── scripts
│ ├── delete_table.py # Python script to delete a table
│ ├── parse_table.py
│ └── yaml_to_json.py # Converts YAML to JSON for create-table
└── table-definitions
└── example_table.yaml
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
4. Push to GitLab
```
git add table-definitions/my_table.yaml
git commit -m "Add new table definition"
git push

```


🗑️ Delete Tables
Simply delete the YAML file:

```
git rm table-definitions/my_table.yaml
git commit -m "Delete my_table"
git push

```

The pipeline will automatically delete the corresponding S3 table.
🧪 Test Locally
```
# Test parse_table.py
python3 scripts/parse_table.py table-definitions/example_table.yaml

# Test yaml_to_json.py
python3 scripts/yaml_to_json.py table-definitions/example_table.yaml output.json

```


📝 Pipeline Stages
delete-tables - Deletes S3 tables for removed YAML files
create-tables - Creates S3 tables from new or modified YAML files
🔐 IAM Permissions Required
```
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

📌 Notes
Fully auditable, central process for table management
Works with Iceberg tables only
All changes are tracked via Git and automated through GitLab CI/CD

