terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

variable "aws_region" { type = string default = "us-east-1" }
variable "environment" { type = string default = "prod" }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "broker_secret_arn" { type = string }

resource "aws_cloudwatch_log_group" "engine" {
  name              = "/quant-engine/${var.environment}"
  retention_in_days = 30
}

resource "aws_secretsmanager_secret" "broker" {
  name = "quant-engine/${var.environment}/broker"
}

resource "aws_db_instance" "postgres" {
  identifier             = "quant-engine-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.medium"
  allocated_storage      = 100
  storage_encrypted      = true
  publicly_accessible    = false
  skip_final_snapshot    = true
  db_subnet_group_name   = aws_db_subnet_group.private.name
}

resource "aws_db_subnet_group" "private" {
  name       = "quant-engine-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_msk_cluster" "events" {
  cluster_name           = "quant-engine-${var.environment}"
  kafka_version           = "3.7.x"
  number_of_broker_nodes = 2
  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    client_subnets  = var.private_subnet_ids
    storage_info { ebs_storage_info { volume_size = 100 } }
  }
  encryption_info { encryption_in_transit { client_broker = "TLS" } }
}

resource "aws_ecs_cluster" "engine" {
  name = "quant-engine-${var.environment}"
  setting { name = "containerInsights" value = "enabled" }
}

resource "aws_iam_role" "ecs_task" {
  name = "quant-engine-${var.environment}-ecs-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = var.broker_secret_arn }] })
}

output "ecs_cluster" { value = aws_ecs_cluster.engine.name }
output "postgres_endpoint" { value = aws_db_instance.postgres.address }
output "msk_cluster_arn" { value = aws_msk_cluster.events.arn }
