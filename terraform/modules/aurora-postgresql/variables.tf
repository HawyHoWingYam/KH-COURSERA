# Variables for Aurora PostgreSQL Module

variable "environment" {
  description = "Environment name (sandbox, uat, production)"
  type        = string
  validation {
    condition     = contains(["sandbox", "uat", "production"], var.environment)
    error_message = "Environment must be one of: sandbox, uat, production."
  }
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "hya-ocr"
}

variable "vpc_id" {
  description = "VPC ID where Aurora cluster will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for Aurora cluster"
  type        = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "At least 2 subnet IDs are required for Aurora cluster."
  }
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "hya_ocr"
}

variable "master_username" {
  description = "Master username for the database"
  type        = string
  default     = "hya_ocr_admin"
}

variable "master_password" {
  description = "Master password for the database"
  type        = string
  sensitive   = true
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to access the database"
  type        = list(string)
  default     = []
}

variable "allowed_security_group_ids" {
  description = "List of security group IDs allowed to access the database"
  type        = list(string)
  default     = []
}

variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
  default     = null
}

variable "monitoring_role_arn" {
  description = "IAM role ARN for enhanced monitoring"
  type        = string
  default     = null
}

# Environment-specific overrides
variable "instance_class_override" {
  description = "Override default instance class for the environment"
  type        = string
  default     = null
}

variable "instance_count_override" {
  description = "Override default instance count for the environment"
  type        = number
  default     = null
}

variable "backup_retention_override" {
  description = "Override default backup retention period"
  type        = number
  default     = null
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = null
}

variable "enable_performance_insights" {
  description = "Enable Performance Insights"
  type        = bool
  default     = null
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}