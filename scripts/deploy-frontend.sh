#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# deploy-frontend.sh — Build the Next.js frontend and deploy to S3/CloudFront
#
# Usage:
#   ./scripts/deploy-frontend.sh
#
# Prerequisites:
#   - AWS CLI configured with the "terraform" profile
#   - Terraform outputs available in infra/
#   - Node.js and npm installed
#
# Requirements: 16.1
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infra"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
AWS_PROFILE="terraform"

echo "==> Resolving Terraform outputs..."

BUCKET_NAME=$(terraform -chdir="$INFRA_DIR" output -raw s3_frontend_bucket_name 2>/dev/null)
if [ -z "$BUCKET_NAME" ]; then
  echo "ERROR: Could not read s3_frontend_bucket_name from Terraform outputs." >&2
  echo "       Run 'terraform apply' in infra/ first." >&2
  exit 1
fi

DISTRIBUTION_ID=$(terraform -chdir="$INFRA_DIR" output -raw cloudfront_distribution_id 2>/dev/null || true)
if [ -z "$DISTRIBUTION_ID" ]; then
  # Fallback: try to get the distribution ID by describing distributions
  echo "    cloudfront_distribution_id output not found, looking up by comment..."
  DISTRIBUTION_ID=$(
    aws cloudfront list-distributions \
      --profile "$AWS_PROFILE" \
      --query "DistributionList.Items[?Comment=='Pranav-meeting-minutes Frontend'].Id | [0]" \
      --output text 2>/dev/null || true
  )
fi

if [ -z "$DISTRIBUTION_ID" ] || [ "$DISTRIBUTION_ID" = "None" ]; then
  echo "WARNING: Could not determine CloudFront distribution ID. Cache invalidation will be skipped." >&2
fi

echo "    Bucket:       $BUCKET_NAME"
echo "    Distribution: ${DISTRIBUTION_ID:-<not found>}"

# ---------------------------------------------------------------------------
# Step 1: Build the Next.js app
# ---------------------------------------------------------------------------
echo ""
echo "==> Building Next.js app..."
cd "$FRONTEND_DIR"
npm run build
echo "    Build output: $FRONTEND_DIR/out/"

# ---------------------------------------------------------------------------
# Step 2: Sync build output to S3
# ---------------------------------------------------------------------------
echo ""
echo "==> Syncing build output to s3://$BUCKET_NAME ..."
aws s3 sync "$FRONTEND_DIR/out/" "s3://$BUCKET_NAME/" \
  --delete \
  --profile "$AWS_PROFILE"
echo "    Sync complete."

# ---------------------------------------------------------------------------
# Step 3: Invalidate CloudFront cache
# ---------------------------------------------------------------------------
if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
  echo ""
  echo "==> Invalidating CloudFront cache..."
  INVALIDATION_ID=$(
    aws cloudfront create-invalidation \
      --distribution-id "$DISTRIBUTION_ID" \
      --paths "/*" \
      --profile "$AWS_PROFILE" \
      --query "Invalidation.Id" \
      --output text
  )
  echo "    Invalidation created: $INVALIDATION_ID"
else
  echo ""
  echo "==> Skipping CloudFront invalidation (no distribution ID)."
fi

echo ""
echo "==> Frontend deployment complete!"
