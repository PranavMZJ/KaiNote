locals {
  common_tags = {
    User    = var.user_name
    Project = var.project_name
  }

  permissions_boundary = "arn:aws:iam::681561127010:policy/MZJTeamBoundary"

  name_prefix       = "${var.user_name}-${var.project_name}"
  name_prefix_lower = lower("${var.user_name}-${var.project_name}")
}
