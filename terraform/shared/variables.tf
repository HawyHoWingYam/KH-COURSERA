# Shared Variables for All Environments

# Project Configuration
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "hya-ocr"
}

variable "project_owner" {
  description = "Project owner for tagging"
  type        = string
  default     = "HYA-OCR-Team"
}

# AWS Configuration
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

# Common tags applied to all resources
variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "HYA-OCR"
    ManagedBy   = "terraform"
    Owner       = "HYA-OCR-Team"
    Application = "GeminiOCR"
  }
}

# Network Configuration (you'll need to adjust these based on your VPC setup)
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
}

# Database Configuration
variable "database_engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "hya_ocr"
}

variable "database_master_username" {
  description = "Master username for the database"
  type        = string
  default     = "hya_ocr_admin"
}

# Environment-specific instance configurations
variable "environment_configs" {
  description = "Environment-specific configurations"
  type = map(object({
    instance_class                = string
    instance_count               = number
    backup_retention_period      = number
    deletion_protection          = bool
    enable_performance_insights  = bool
    monitoring_interval          = number
    preferred_backup_window      = string
    preferred_maintenance_window = string
  }))
  default = {
    sandbox = {
      instance_class                = "db.t3.medium"
      instance_count               = 1
      backup_retention_period      = 7
      deletion_protection          = false
      enable_performance_insights  = false
      monitoring_interval          = 0
      preferred_backup_window      = "03:00-04:00"
      preferred_maintenance_window = "sun:02:00-sun:03:00"
    }
    uat = {
      instance_class                = "db.r5.large"
      instance_count               = 2
      backup_retention_period      = 14
      deletion_protection          = false
      enable_performance_insights  = true
      monitoring_interval          = 60
      preferred_backup_window      = "03:00-04:00"
      preferred_maintenance_window = "sun:03:00-sun:04:00"
    }
    production = {
      instance_class                = "db.r5.xlarge"
      instance_count               = 3
      backup_retention_period      = 30
      deletion_protection          = true
      enable_performance_insights  = true
      monitoring_interval          = 15
      preferred_backup_window      = "03:00-04:00"
      preferred_maintenance_window = "sun:04:00-sun:05:00"
    }
  }
}