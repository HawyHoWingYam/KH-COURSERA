terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "name" { type = string }
variable "engine_version" { type = string  default = "15" }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_sg_ids" { type = list(string)  description = "App SGs allowed to access 5432" }
variable "secret_name" { type = string  description = "Secrets Manager name to store database_url" }
variable "backup_retention" { type = number default = 3 }

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-subnet-group"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "aurora" {
  name        = "${var.name}-aurora-sg"
  description = "Aurora access"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "allow_app_sg" {
  for_each                 = toset(var.allowed_sg_ids)
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = each.value
  security_group_id        = aws_security_group.aurora.id
}

resource "aws_rds_cluster" "this" {
  cluster_identifier      = var.name
  engine                  = "aurora-postgresql"
  engine_version          = var.engine_version
  database_name           = "postgres"
  # Use variables; do not hardcode credentials
  master_username         = var.master_username
  master_password         = var.master_password
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.aurora.id]
  backup_retention_period = var.backup_retention
}

resource "aws_rds_cluster_instance" "this" {
  identifier         = "${var.name}-instance-1"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
}

resource "aws_secretsmanager_secret" "db" {
  name = var.secret_name
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  # Store a connection string constructed from variables; the actual secret value
  # is provided at apply time via Terraform variables or a secure pipeline.
  secret_string = jsonencode({
    database_url = "postgresql://${var.master_username}:${var.master_password}@${aws_rds_cluster.this.endpoint}:5432/postgres?sslmode=require"
  })
}

output "cluster_endpoint" { value = aws_rds_cluster.this.endpoint }
output "security_group_id" { value = aws_security_group.aurora.id }
output "secret_arn" { value = aws_secretsmanager_secret.db.arn }
