# Outputs for Sandbox Environment

# Database connection information
output "database_connection_info" {
  description = "Database connection information for applications"
  value = {
    host                = module.aurora_postgresql.cluster_endpoint
    readonly_host       = module.aurora_postgresql.cluster_reader_endpoint
    port                = module.aurora_postgresql.cluster_port
    database            = module.aurora_postgresql.database_name
    username            = module.aurora_postgresql.master_username
    cluster_identifier  = module.aurora_postgresql.cluster_identifier
  }
}

# Complete DATABASE_URL for easy application configuration
output "database_url" {
  description = "Complete DATABASE_URL for application configuration"
  value       = module.aurora_postgresql.database_url
  sensitive   = true
}

output "readonly_database_url" {
  description = "Read-only DATABASE_URL for application configuration"
  value       = module.aurora_postgresql.readonly_database_url
  sensitive   = true
}

# Secrets Manager information
output "secrets_manager_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.database_credentials.arn
}

output "secrets_manager_name" {
  description = "Name of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.database_credentials.name
}

# Security Group IDs for application configuration
output "app_security_group_id" {
  description = "Security group ID for applications that need database access"
  value       = aws_security_group.app_access.id
}

output "database_security_group_id" {
  description = "Security group ID of the Aurora cluster"
  value       = module.aurora_postgresql.security_group_id
}

# Cluster information
output "cluster_arn" {
  description = "Amazon Resource Name (ARN) of the Aurora cluster"
  value       = module.aurora_postgresql.cluster_arn
}

output "cluster_members" {
  description = "List of RDS instances that are part of this cluster"
  value       = module.aurora_postgresql.cluster_members
}

output "instance_endpoints" {
  description = "List of all instance endpoints"
  value       = module.aurora_postgresql.instance_endpoints
}

# Monitoring and logging
output "cloudwatch_log_group" {
  description = "CloudWatch log group for Aurora PostgreSQL logs"
  value       = module.aurora_postgresql.cloudwatch_log_group_name
}

output "monitoring_role_arn" {
  description = "IAM role ARN for enhanced monitoring"
  value       = aws_iam_role.rds_enhanced_monitoring.arn
}

# Encryption information
output "kms_key_id" {
  description = "KMS key ID used for Aurora encryption"
  value       = aws_kms_key.aurora_kms_key.key_id
}

output "kms_key_arn" {
  description = "KMS key ARN used for Aurora encryption"
  value       = aws_kms_key.aurora_kms_key.arn
}

# Network information
output "vpc_id" {
  description = "VPC ID where Aurora is deployed"
  value       = data.aws_vpc.existing.id
}

output "subnet_ids" {
  description = "Subnet IDs used by Aurora"
  value       = data.aws_subnets.database.ids
}

# Environment information
output "environment" {
  description = "Environment name"
  value       = "sandbox"
}

output "region" {
  description = "AWS region"
  value       = var.aws_region
}

# Configuration for application deployment
output "application_config" {
  description = "Configuration values for application deployment"
  value = {
    DATABASE_HOST     = module.aurora_postgresql.cluster_endpoint
    DATABASE_PORT     = module.aurora_postgresql.cluster_port
    DATABASE_NAME     = module.aurora_postgresql.database_name
    DATABASE_USER     = module.aurora_postgresql.master_username
    READONLY_HOST     = module.aurora_postgresql.cluster_reader_endpoint
    SECRETS_ARN       = aws_secretsmanager_secret.database_credentials.arn
    SECURITY_GROUP_ID = aws_security_group.app_access.id
    VPC_ID           = data.aws_vpc.existing.id
  }
  sensitive = true
}

# Cost tracking tags
output "cost_tags" {
  description = "Tags for cost tracking and resource management"
  value = merge(var.common_tags, {
    Environment = "sandbox"
    CostCenter  = var.cost_center
    AutoManaged = "terraform"
  })
}