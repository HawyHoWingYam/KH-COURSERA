terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

module "aurora" {
  source         = "../../modules/aurora-postgresql"
  name           = "geminiocr-sandbox"
  engine_version = var.engine_version
  vpc_id         = var.vpc_id
  subnet_ids     = var.subnet_ids
  allowed_sg_ids = var.allowed_sg_ids
  secret_name    = var.secret_name
  backup_retention = 1
}

output "endpoint" { value = module.aurora.cluster_endpoint }
output "secret_arn" { value = module.aurora.secret_arn }

