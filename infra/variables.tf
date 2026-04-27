variable "region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name used in resource naming and tagging"
  type        = string
  default     = "meeting-minutes"
}

variable "user_name" {
  description = "User name used in resource naming and tagging"
  type        = string
  default     = "Pranav"
}
