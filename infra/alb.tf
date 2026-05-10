# ------------------------------------------------------------------------------
# Application Load Balancer — Transcription Service
# Internet-facing ALB for WebSocket connections to Fargate
# ------------------------------------------------------------------------------

# ==============================================================================
# ALB
# ==============================================================================

resource "aws_lb" "transcription" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-transcription-alb"
  })
}

# ==============================================================================
# Target Group
# ==============================================================================

resource "aws_lb_target_group" "transcription" {
  name        = "${local.name_prefix}-tg2"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  stickiness {
    type    = "lb_cookie"
    enabled = true
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = local.common_tags
}

# ==============================================================================
# Listener (HTTP — port 80)
# ==============================================================================

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.transcription.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.transcription.arn
  }

  tags = local.common_tags
}

# ==============================================================================
# Security Groups
# ==============================================================================

# --- ALB Security Group ---
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Allow inbound HTTP/HTTPS to ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb-sg"
  })
}

# --- ECS Security Group ---
resource "aws_security_group" "ecs" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "Allow inbound from ALB on port 8080"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "From ALB on port 8080"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-sg"
  })
}
