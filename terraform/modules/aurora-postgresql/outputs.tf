# Outputs for Aurora PostgreSQL Module

output "cluster_identifier" {
  description = "The RDS cluster identifier"
  value       = aws_rds_cluster.aurora_cluster.cluster_identifier
}

output "cluster_endpoint" {
  description = "Writer endpoint for the cluster"
  value       = aws_rds_cluster.aurora_cluster.endpoint
}

output "cluster_reader_endpoint" {
  description = "Reader endpoint for the cluster"
  value       = aws_rds_cluster.aurora_cluster.reader_endpoint
}

output "cluster_port" {
  description = "The database port"
  value       = aws_rds_cluster.aurora_cluster.port
}

output "database_name" {
  description = "The name of the database"
  value       = aws_rds_cluster.aurora_cluster.database_name
}

output "master_username" {
  description = "The master username for the database"
  value       = aws_rds_cluster.aurora_cluster.master_username
  sensitive   = true
}

output "cluster_arn" {
  description = "Amazon Resource Name (ARN) of cluster"
  value       = aws_rds_cluster.aurora_cluster.arn
}

output "cluster_members" {
  description = "List of RDS Instances that are a part of this cluster"
  value       = aws_rds_cluster.aurora_cluster.cluster_members
}

output "security_group_id" {
  description = "The security group ID of the cluster"
  value       = aws_security_group.aurora_security_group.id
}

output "subnet_group_name" {
  description = "The name of the DB subnet group"
  value       = aws_db_subnet_group.aurora_subnet_group.name
}

# Connection information for applications
output "connection_info" {
  description = "Database connection information"
  value = {
    host     = aws_rds_cluster.aurora_cluster.endpoint
    port     = aws_rds_cluster.aurora_cluster.port
    database = aws_rds_cluster.aurora_cluster.database_name
    username = aws_rds_cluster.aurora_cluster.master_username
  }
  sensitive = true
}

# Read-only connection information
output "readonly_connection_info" {
  description = "Read-only database connection information"
  value = {
    host     = aws_rds_cluster.aurora_cluster.reader_endpoint
    port     = aws_rds_cluster.aurora_cluster.port
    database = aws_rds_cluster.aurora_cluster.database_name
    username = aws_rds_cluster.aurora_cluster.master_username
  }
  sensitive = true
}

# Instance information
output "instance_identifiers" {
  description = "List of instance identifiers"
  value       = aws_rds_cluster_instance.aurora_instance[*].identifier
}

output "instance_endpoints" {
  description = "List of instance endpoints"
  value       = aws_rds_cluster_instance.aurora_instance[*].endpoint
}

# CloudWatch Log Group
output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.aurora_logs.name
}

# Environment-specific outputs
output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "backup_retention_period" {
  description = "Backup retention period in days"
  value       = aws_rds_cluster.aurora_cluster.backup_retention_period
}

output "preferred_backup_window" {
  description = "Preferred backup window"
  value       = aws_rds_cluster.aurora_cluster.preferred_backup_window
}

output "preferred_maintenance_window" {
  description = "Preferred maintenance window"
  value       = aws_rds_cluster.aurora_cluster.preferred_maintenance_window
}

# For DATABASE_URL construction
output "database_url" {
  description = "Complete DATABASE_URL for application configuration"
  value       = "postgresql://${aws_rds_cluster.aurora_cluster.master_username}:${var.master_password}@${aws_rds_cluster.aurora_cluster.endpoint}:${aws_rds_cluster.aurora_cluster.port}/${aws_rds_cluster.aurora_cluster.database_name}"
  sensitive   = true
}

output "readonly_database_url" {
  description = "Complete read-only DATABASE_URL for application configuration"
  value       = "postgresql://${aws_rds_cluster.aurora_cluster.master_username}:${var.master_password}@${aws_rds_cluster.aurora_cluster.reader_endpoint}:${aws_rds_cluster.aurora_cluster.port}/${aws_rds_cluster.aurora_cluster.database_name}"
  sensitive   = true
}