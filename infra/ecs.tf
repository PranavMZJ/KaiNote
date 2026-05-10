# ------------------------------------------------------------------------------
# ECS EC2 — Transcription Service
# Uses t3.micro EC2 instance instead of Fargate for cost optimization
# Container runs on ECS-optimized AMI in private subnet (NAT for outbound)
# ------------------------------------------------------------------------------

# ==============================================================================
# ECS Cluster
# ==============================================================================

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

# ==============================================================================
# ECR Repository
# ==============================================================================

resource "aws_ecr_repository" "transcription" {
  name         = "${local.name_prefix_lower}-transcription-service"
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# ==============================================================================
# CloudWatch Log Group
# ==============================================================================

resource "aws_cloudwatch_log_group" "transcription" {
  name              = "/ecs/${local.name_prefix}-transcription"
  retention_in_days = 14

  tags = local.common_tags
}

# ==============================================================================
# ECS-Optimized AMI (Amazon Linux 2023, x86_64)
# ==============================================================================

data "aws_ssm_parameter" "ecs_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id"
}

# ==============================================================================
# EC2 Instance Profile (allows EC2 to join ECS cluster)
# ==============================================================================

resource "aws_iam_role" "ecs_instance" {
  name                 = "${local.name_prefix}-ecs-instance-role"
  assume_role_policy   = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
  permissions_boundary = local.permissions_boundary

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_instance_policy" {
  role       = aws_iam_role.ecs_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "ecs_instance" {
  name = "${local.name_prefix}-ecs-instance-profile"
  role = aws_iam_role.ecs_instance.name

  tags = local.common_tags
}

# ==============================================================================
# EC2 Instance (t3.micro — ECS container host)
# ==============================================================================

resource "aws_instance" "ecs_host" {
  ami                    = data.aws_ssm_parameter.ecs_ami.value
  instance_type          = "t3.micro"
  iam_instance_profile   = aws_iam_instance_profile.ecs_instance.name
  subnet_id              = aws_subnet.private_1.id
  vpc_security_group_ids = [aws_security_group.ecs.id]

  user_data = base64encode(<<-EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${aws_ecs_cluster.main.name}" >> /etc/ecs/ecs.config
  EOF
  )

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-host"
  })
}

# ==============================================================================
# ECS Task Definition (EC2 launch type)
# ==============================================================================

resource "aws_ecs_task_definition" "transcription" {
  family                   = "${local.name_prefix}-transcription"
  network_mode             = "bridge"
  requires_compatibilities = ["EC2"]
  execution_role_arn       = aws_iam_role.ecs_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "transcription-service"
      image     = "${aws_ecr_repository.transcription.repository_url}:latest"
      essential = true
      memory    = 768
      cpu       = 512

      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "TRANSCRIPT_BUCKET"
          value = aws_s3_bucket.data.id
        },
        {
          name  = "STEP_FUNCTION_ARN"
          value = aws_sfn_state_machine.workflow.arn
        },
        {
          name  = "MEETINGS_TABLE"
          value = aws_dynamodb_table.meetings.name
        },
        {
          name  = "AWS_REGION"
          value = "ap-northeast-1"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.transcription.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = local.common_tags
}

# ==============================================================================
# ECS Service (EC2 launch type)
# ==============================================================================

resource "aws_ecs_service" "transcription" {
  name            = "${local.name_prefix}-transcription-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.transcription.arn
  desired_count   = 1
  launch_type     = "EC2"

  health_check_grace_period_seconds = 120

  load_balancer {
    target_group_arn = aws_lb_target_group.transcription.arn
    container_name   = "transcription-service"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.http, aws_instance.ecs_host]

  tags = local.common_tags
}
