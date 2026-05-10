#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Deploy Transcription Service to ECS (EC2 mode)
# Builds Docker image, pushes to ECR, and forces a new ECS deployment.
# ---------------------------------------------------------------------------

AWS_PROFILE="terraform"
AWS_REGION="ap-northeast-1"
ECR_REPO=$(terraform -chdir=infra output -raw ecr_repository_url)
CLUSTER=$(terraform -chdir=infra output -raw ecs_cluster_name)
SERVICE=$(terraform -chdir=infra output -raw ecs_service_name)

echo "=== KaiNote Transcription Service Deployment ==="
echo "ECR Repo: $ECR_REPO"
echo "Cluster:  $CLUSTER"
echo "Service:  $SERVICE"
echo ""

# Build for linux/amd64 (EC2 t3.micro runs x86_64)
echo "Building Docker image for linux/amd64..."
docker build --platform linux/amd64 -t kainote-transcription services/transcription/

# Tag
echo "Tagging image for ECR..."
docker tag kainote-transcription:latest "$ECR_REPO:latest"

# Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --profile "$AWS_PROFILE" --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$(echo "$ECR_REPO" | cut -d/ -f1)"

# Push
echo "Pushing image to ECR..."
docker push "$ECR_REPO:latest"

# Force new deployment
echo "Forcing new ECS deployment..."
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --force-new-deployment \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --query "service.serviceName" \
  --output text

echo ""
echo "Deployment started. Service: $SERVICE"
echo "Monitor: aws ecs describe-services --cluster $CLUSTER --services $SERVICE --profile $AWS_PROFILE --region $AWS_REGION --query 'services[0].deployments'"
