---
inclusion: auto
---

# MZJ-IAM Naming and Tagging Conventions

This project operates under MZJ-IAM policies. All generated code, Terraform configurations, and AWS CLI commands must follow these rules. Violations will be rejected by AWS IAM at apply time.

## Required Tags

Every AWS resource must include both of these tags:

| Tag Key   | Value                                  |
|-----------|----------------------------------------|
| `User`    | `Pranav`                               |
| `Project` | `meeting-minutes`    |

In Terraform, define these as a `locals` block and pass them to every module:

```hcl
locals {
  common_tags = {
    User    = "Pranav"
    Project = "meeting-minutes"
  }
}
```

## Resource Naming

All resource names follow this pattern:

```
Pranav-meeting-minutes-<purpose>
```

Examples:
- Lambda function: `Pranav-meeting-minutes`
- IAM role: `Pranav-meeting-minutes-role`
- DynamoDB table: `Pranav-meeting-minutes-items`

### S3 Bucket Names

S3 bucket names must be **lowercase** (AWS requirement):

```
pranav-meeting-minutes-<purpose>
```

## IAM Permissions Boundary

Every IAM role must have the MZJTeamBoundary attached as a permissions boundary. Roles created without this boundary will be rejected by AWS.

```
arn:aws:iam::681561127010:policy/MZJTeamBoundary
```

In Terraform:

```hcl
resource "aws_iam_role" "example" {
  name                 = "Pranav-meeting-minutes-<purpose>"
  permissions_boundary = "arn:aws:iam::681561127010:policy/MZJTeamBoundary"
  # ...
}
```

## Terraform Provider Configuration

Always use these provider settings:

```hcl
provider "aws" {
  region  = "ap-northeast-1"
  profile = "terraform"
}
```

- **Profile**: `terraform`
- **Region**: `ap-northeast-1`
