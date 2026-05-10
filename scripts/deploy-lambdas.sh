#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# deploy-lambdas.sh — Package and deploy all 9 Lambda functions
#
# This script:
#   1. Creates a Lambda layer with Python dependencies (if not already done)
#   2. Attaches the layer to all 9 Lambda functions
#   3. Packages each Lambda handler WITH shared modules (models/, utils/)
#   4. Deploys the code to each Lambda function
#
# Usage:
#   ./scripts/deploy-lambdas.sh
#
# Prerequisites:
#   - AWS CLI configured with the "terraform" profile
#   - Python 3.12 and pip installed
#   - Terraform infrastructure already deployed (terraform apply)
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
BUILD_DIR="$PROJECT_ROOT/infra/.build"
AWS_PROFILE="terraform"
AWS_REGION="ap-northeast-1"
LAYER_NAME="Pranav-meeting-minutes-deps"
FUNCTION_PREFIX="Pranav-meeting-minutes"

# Lambda name → source directory mapping
# Format: "lambda-suffix:source-folder"
LAMBDAS=(
  "ws-authorizer:ws_authorizer"
  "ws-handler:ws_handler"
  "stream-bridge:stream_bridge"
  "api:api"
  "cleanup:cleanup"
  "chunker:chunker"
  "generator:generator"
  "validator:validator"
  "store:store"
  "agent:agent"
)

mkdir -p "$BUILD_DIR"

echo "=============================================="
echo "  Meeting Minutes — Lambda Deployment Script"
echo "=============================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo "AWS Profile:  $AWS_PROFILE"
echo "AWS Region:   $AWS_REGION"
echo ""

# =============================================
# STEP 1: Create Lambda Layer (if needed)
# =============================================

echo "==> Step 1: Checking Lambda layer..."

EXISTING_LAYER=$(aws lambda list-layer-versions \
  --layer-name "$LAYER_NAME" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --query "LayerVersions[0].LayerVersionArn" \
  --output text 2>/dev/null || echo "None")

if [ "$EXISTING_LAYER" = "None" ] || [ -z "$EXISTING_LAYER" ]; then
  echo "    Layer not found. Creating..."

  LAYER_DIR="$PROJECT_ROOT/layer"
  rm -rf "$LAYER_DIR"
  mkdir -p "$LAYER_DIR/python"

  echo "    Installing dependencies into layer..."
  pip install -r "$BACKEND_DIR/requirements.txt" \
    -t "$LAYER_DIR/python/" \
    --quiet --no-cache-dir

  echo "    Zipping layer..."
  cd "$LAYER_DIR"
  zip -r "$PROJECT_ROOT/lambda-layer.zip" python/ -q
  cd "$PROJECT_ROOT"

  echo "    Publishing layer..."
  LAYER_OUTPUT=$(aws lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --zip-file "fileb://lambda-layer.zip" \
    --compatible-runtimes python3.12 \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --output json)

  LAYER_ARN=$(echo "$LAYER_OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['LayerVersionArn'])")
  echo "    Layer published: $LAYER_ARN"

  # Cleanup
  rm -rf "$LAYER_DIR" "$PROJECT_ROOT/lambda-layer.zip"
else
  LAYER_ARN="$EXISTING_LAYER"
  echo "    Layer already exists: $LAYER_ARN"
fi

echo ""

# =============================================
# STEP 2: Attach layer to all Lambda functions
# =============================================

echo "==> Step 2: Attaching layer to all Lambda functions..."

for entry in "${LAMBDAS[@]}"; do
  LAMBDA_SUFFIX="${entry%%:*}"
  FUNCTION_NAME="${FUNCTION_PREFIX}-${LAMBDA_SUFFIX}"

  echo "    Attaching layer to ${FUNCTION_NAME}..."
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --layers "$LAYER_ARN" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --output text \
    --query "FunctionName" > /dev/null 2>&1
done

echo "    Layer attached to all 10 functions."
echo ""

# Wait for all function updates to complete
echo "    Waiting for function updates to stabilize..."
sleep 10

# =============================================
# STEP 3: Package and deploy each Lambda
# =============================================

echo "==> Step 3: Packaging and deploying Lambda functions..."
echo ""

for entry in "${LAMBDAS[@]}"; do
  LAMBDA_SUFFIX="${entry%%:*}"
  SOURCE_FOLDER="${entry##*:}"
  FUNCTION_NAME="${FUNCTION_PREFIX}-${LAMBDA_SUFFIX}"
  ZIP_FILE="${BUILD_DIR}/${LAMBDA_SUFFIX}.zip"
  HANDLER_DIR="${BACKEND_DIR}/lambdas/${SOURCE_FOLDER}"

  echo "  --- ${FUNCTION_NAME} ---"

  # Verify handler exists
  if [ ! -f "${HANDLER_DIR}/handler.py" ]; then
    echo "    ERROR: ${HANDLER_DIR}/handler.py not found. Skipping."
    echo ""
    continue
  fi

  # Create a temporary staging directory
  STAGING_DIR="${BUILD_DIR}/staging-${LAMBDA_SUFFIX}"
  rm -rf "$STAGING_DIR"
  mkdir -p "$STAGING_DIR"

  # Copy the handler
  cp "${HANDLER_DIR}/handler.py" "$STAGING_DIR/"

  # Copy shared modules (models/, utils/) that handlers import
  # These are imported as "backend.models.*" and "backend.utils.*"
  # so we need to preserve the package structure
  mkdir -p "$STAGING_DIR/backend/models"
  mkdir -p "$STAGING_DIR/backend/utils"
  mkdir -p "$STAGING_DIR/backend/lambdas/${SOURCE_FOLDER}"

  # Copy backend package init
  cp "${BACKEND_DIR}/__init__.py" "$STAGING_DIR/backend/"

  # Copy models
  cp "${BACKEND_DIR}/models/__init__.py" "$STAGING_DIR/backend/models/"
  cp "${BACKEND_DIR}/models/transcript.py" "$STAGING_DIR/backend/models/"
  cp "${BACKEND_DIR}/models/minutes.py" "$STAGING_DIR/backend/models/"
  cp "${BACKEND_DIR}/models/meeting_status.py" "$STAGING_DIR/backend/models/"

  # Copy utils
  cp "${BACKEND_DIR}/utils/__init__.py" "$STAGING_DIR/backend/utils/"
  cp "${BACKEND_DIR}/utils/s3_keys.py" "$STAGING_DIR/backend/utils/"

  # Copy lambdas init and the specific handler as a package
  if [ -f "${BACKEND_DIR}/lambdas/__init__.py" ]; then
    mkdir -p "$STAGING_DIR/backend/lambdas"
    cp "${BACKEND_DIR}/lambdas/__init__.py" "$STAGING_DIR/backend/lambdas/"
    cp "${HANDLER_DIR}/handler.py" "$STAGING_DIR/backend/lambdas/${SOURCE_FOLDER}/handler.py"
    if [ -f "${HANDLER_DIR}/__init__.py" ]; then
      cp "${HANDLER_DIR}/__init__.py" "$STAGING_DIR/backend/lambdas/${SOURCE_FOLDER}/"
    else
      touch "$STAGING_DIR/backend/lambdas/${SOURCE_FOLDER}/__init__.py"
    fi
  fi

  # Create the zip
  cd "$STAGING_DIR"
  zip -r "$ZIP_FILE" . -q
  cd "$PROJECT_ROOT"

  ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
  echo "    Packaged: ${ZIP_FILE} (${ZIP_SIZE})"

  # Wait for any pending updates on this function
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" 2>/dev/null || true

  # Deploy
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://${ZIP_FILE}" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --output text \
    --query "FunctionName" > /dev/null 2>&1

  echo "    Deployed: ${FUNCTION_NAME} ✓"

  # Cleanup staging
  rm -rf "$STAGING_DIR"
  echo ""
done

# =============================================
# DONE
# =============================================

echo "=============================================="
echo "  All 10 Lambda functions deployed!"
echo "=============================================="
echo ""
echo "Functions deployed:"
for entry in "${LAMBDAS[@]}"; do
  LAMBDA_SUFFIX="${entry%%:*}"
  echo "  ✓ ${FUNCTION_PREFIX}-${LAMBDA_SUFFIX}"
done
echo ""
echo "Layer: ${LAYER_ARN}"
echo ""
