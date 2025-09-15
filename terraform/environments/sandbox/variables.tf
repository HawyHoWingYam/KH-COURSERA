variable "region" { type = string }
variable "engine_version" { type = string  default = "15" }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_sg_ids" { type = list(string) }
variable "secret_name" { type = string  default = "sandbox/database" }

