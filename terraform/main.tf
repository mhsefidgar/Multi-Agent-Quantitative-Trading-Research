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
variable "container_image" { type = string default = "public.ecr.aws/docker/library/python:3.11-slim" }
variable "desired_count" { type = number default = 1 }

resource "aws_cloudwatch_log_group" "engine" {
  name              = "/quant-engine/${var.environment}"
  retention_in_days = 30
}

resource "aws_secretsmanager_secret" "broker" {
  name = "quant-engine/${var.environment}/broker"
}

resource "aws_security_group" "data" {
  name   = "quant-engine-${var.environment}-data"
  vpc_id = var.vpc_id

  ingress { from_port = 5432 to_port = 5432 protocol = "tcp" cidr_blocks = [] security_groups = [aws_security_group.tasks.id] }
  ingress { from_port = 9094 to_port = 9094 protocol = "tcp" cidr_blocks = [] security_groups = [aws_security_group.tasks.id] }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "tasks" {
  name   = "quant-engine-${var.environment}-tasks"
  vpc_id = var.vpc_id
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_db_subnet_group" "private" {
  name       = "quant-engine-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "postgres" {
  identifier           = "quant-engine-${var.environment}"
  engine               = "postgres"
  engine_version       = "16"
  instance_class       = "db.t4g.medium"
  allocated_storage    = 100
  storage_encrypted    = true
  publicly_accessible  = false
  skip_final_snapshot  = true
  db_subnet_group_name = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.data.id]
}

resource "aws_msk_cluster" "events" {
  cluster_name           = "quant-engine-${var.environment}"
  kafka_version           = "3.7.x"
  number_of_broker_nodes = 2
  broker_node_group_info {
    instance_type  = "kafka.t3.small"
    client_subnets = var.private_subnet_ids
    security_groups = [aws_security_group.data.id]
    storage_info { ebs_storage_info { volume_size = 100 } }
  }
  encryption_info { encryption_in_transit { client_broker = "TLS" } }
}

resource "aws_ecs_cluster" "engine" {
  name = "quant-engine-${var.environment}"
  setting { name = "containerInsights" value = "enabled" }
}

resource "aws_ecr_repository" "engine" {
  name                 = "quant-engine"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_iam_role" "ecs_task" {
  name = "quant-engine-${var.environment}-ecs-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy" "secrets" {
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [var.broker_secret_arn, aws_secretsmanager_secret.broker.arn] }] })
}

resource "aws_ecs_task_definition" "engine" {
  family                   = "quant-engine-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_task.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name      = "quant-engine"
    image     = var.container_image
    essential = true
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "OTEL_SERVICE_NAME", value = "quant-engine" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.engine.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "engine"
      }
    }
  }])
}

resource "aws_ecs_service" "engine" {
  name            = "quant-engine-${var.environment}"
  cluster         = aws_ecs_cluster.engine.id
  task_definition = aws_ecs_task_definition.engine.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }
}

output "ecs_cluster" { value = aws_ecs_cluster.engine.name }
output "ecs_service" { value = aws_ecs_service.engine.name }
output "ecr_repository" { value = aws_ecr_repository.engine.repository_url }
output "postgres_endpoint" { value = aws_db_instance.postgres.address }
output "msk_cluster_arn" { value = aws_msk_cluster.events.arn }
