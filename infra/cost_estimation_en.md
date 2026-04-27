# Meeting Minutes — AWS Cost Estimation

Region: `ap-northeast-1` (Tokyo) | Pricing model: On-Demand | Currency: USD

All prices sourced from the [AWS Pricing API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html) for `ap-northeast-1` as of April 2026. Bedrock pricing sourced from the [Amazon Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/). Content was rephrased for compliance with licensing restrictions.

## Usage Assumptions

The estimates below are based on a **small-team MVP scenario**:

| Parameter | Value |
|-----------|-------|
| Active users per month | 5 |
| Meetings per user per month | 20 |
| Total meetings per month | 100 |
| Average meeting duration | 30 minutes (1,800 seconds) |
| Average transcript size | 5,000 tokens (~4 KB JSON) |
| Average report size | 3 KB JSON |
| Frontend page views per month | 2,000 |
| Frontend asset size | ~5 MB total |

## Per-Service Cost Breakdown

### 1. Amazon Transcribe Streaming

Transcribe Streaming is billed per second of audio processed.

| Metric | Value |
|--------|-------|
| Unit price | $0.0004/second (first 250K min) |
| Audio per meeting | 1,800 seconds |
| Meetings per month | 100 |
| Total seconds | 180,000 |
| **Monthly cost** | 180,000 × $0.0004 = **$72.00** |

> Transcribe Streaming is the largest cost driver. For lower usage (e.g., 20 meetings/month), this drops to ~$14.40.

### 2. Amazon Bedrock (Claude 3 Haiku)

Bedrock charges per input/output token for on-demand inference.

| Metric | Value |
|--------|-------|
| Input token price | $0.00025 per 1K tokens |
| Output token price | $0.00125 per 1K tokens |
| Input tokens per meeting | ~5,000 (transcript) + ~1,000 (prompt) = 6,000 |
| Output tokens per meeting | ~2,000 (report JSON) |
| Meetings per month | 100 |
| Total input tokens | 600,000 |
| Total output tokens | 200,000 |
| Input cost | 600 × $0.00025 = $0.15 |
| Output cost | 200 × $0.00125 = $0.25 |
| **Monthly cost** | **$0.40** |

> Bedrock with Claude 3 Haiku is very cost-effective for structured extraction tasks.

### 3. AWS Lambda

Lambda charges per request and per GB-second of compute.

| Metric | Value |
|--------|-------|
| Request price | $0.20 per 1M requests |
| Compute price | $0.0000166667 per GB-second |
| Requests per meeting | ~15 (WebSocket messages + workflow steps + API calls) |
| Total requests/month | 100 × 15 = 1,500 |
| Avg duration per request | 2 seconds |
| Avg memory | 0.5 GB (weighted across all Lambdas) |
| Total GB-seconds | 1,500 × 2 × 0.5 = 1,500 |
| Request cost | 1,500 × $0.0000002 = $0.0003 |
| Compute cost | 1,500 × $0.0000166667 = $0.025 |
| **Monthly cost** | **$0.03** |

> Lambda free tier includes 1M requests and 400,000 GB-seconds/month. At this scale, Lambda is effectively free.

### 4. Amazon API Gateway

REST API and WebSocket API are billed separately.

| Component | Unit Price | Usage | Cost |
|-----------|-----------|-------|------|
| REST API requests | $4.25 per 1M requests | ~500 requests/month | $0.002 |
| WebSocket messages | $1.26 per 1M messages | ~100,000 messages/month (audio chunks) | $0.13 |
| WebSocket connection minutes | $0.315 per 1M minutes | 100 × 30 = 3,000 minutes | $0.001 |
| **Monthly cost** | | | **$0.13** |

### 5. Amazon S3

S3 charges for storage and requests.

| Component | Unit Price | Usage | Cost |
|-----------|-----------|-------|------|
| Storage (Standard) | $0.025 per GB-month | ~0.5 GB (transcripts + reports) | $0.013 |
| PUT requests | $0.0047 per 1K requests | ~300 PUTs/month | $0.001 |
| GET requests | $0.00037 per 1K requests | ~500 GETs/month | $0.0002 |
| **Monthly cost** | | | **$0.01** |

### 6. Amazon DynamoDB

On-demand (pay-per-request) mode for the connections table.

| Component | Unit Price | Usage | Cost |
|-----------|-----------|-------|------|
| Write request units | $0.715 per 1M WRUs | ~200 writes/month | $0.0001 |
| Read request units | $0.143 per 1M RRUs | ~500 reads/month | $0.0001 |
| Storage | $0.285 per GB-month | < 1 MB | $0.0003 |
| **Monthly cost** | | | **< $0.01** |

### 7. AWS Step Functions

Standard workflow charges per state transition.

| Metric | Value |
|--------|-------|
| Unit price | $0.025 per 1K state transitions |
| Transitions per meeting | ~10 (7 states + retries) |
| Total transitions/month | 100 × 10 = 1,000 |
| **Monthly cost** | 1,000 × $0.000025 = **$0.03** |

> Step Functions free tier includes 4,000 state transitions/month.

### 8. Amazon Cognito

Cognito User Pools pricing is based on monthly active users (MAUs).

| Metric | Value |
|--------|-------|
| Free tier | First 50,000 MAUs free (Essentials tier) |
| Active users | 5 |
| **Monthly cost** | **$0.00** (within free tier) |

### 9. Amazon CloudFront

CloudFront charges for data transfer and requests.

| Component | Estimate | Cost |
|-----------|----------|------|
| Data transfer out (Japan) | ~10 GB/month | ~$1.14 (at $0.114/GB for first 10 TB) |
| HTTPS requests | ~10,000/month | ~$0.01 |
| **Monthly cost** | | **~$1.15** |

### 10. Amazon Bedrock Guardrails

Guardrails are charged per text unit (1,000 characters) processed.

| Metric | Value |
|--------|-------|
| Unit price | ~$0.75 per 1K text units |
| Text units per meeting | ~10 (input + output) |
| Total text units/month | 1,000 |
| **Monthly cost** | **~$0.75** |

### 11. Amazon CloudWatch

CloudWatch charges for log ingestion and storage.

| Component | Unit Price | Usage | Cost |
|-----------|-----------|-------|------|
| Log ingestion | $0.76 per GB | ~0.1 GB/month | $0.08 |
| Log storage | $0.033 per GB-month | ~0.3 GB (30-day retention) | $0.01 |
| **Monthly cost** | | | **$0.09** |

## Monthly Cost Summary

| Service | Monthly Cost (USD) | % of Total |
|---------|-------------------|------------|
| Amazon Transcribe Streaming | $72.00 | 96.5% |
| Amazon CloudFront | $1.15 | 1.5% |
| Amazon Bedrock Guardrails | $0.75 | 1.0% |
| Amazon Bedrock (Claude 3 Haiku) | $0.40 | 0.5% |
| Amazon API Gateway | $0.13 | 0.2% |
| Amazon CloudWatch | $0.09 | 0.1% |
| AWS Lambda | $0.03 | < 0.1% |
| AWS Step Functions | $0.03 | < 0.1% |
| Amazon S3 | $0.01 | < 0.1% |
| Amazon DynamoDB | < $0.01 | < 0.1% |
| Amazon Cognito | $0.00 | 0% |
| **Total** | **~$74.59** | **100%** |

## Scaling Scenarios

| Scenario | Meetings/Month | Transcribe | Bedrock | Other | Total |
|----------|---------------|------------|---------|-------|-------|
| Solo developer (testing) | 10 | $7.20 | $0.04 | ~$2.50 | **~$9.74** |
| Small team (5 users) | 100 | $72.00 | $0.40 | ~$2.19 | **~$74.59** |
| Medium team (20 users) | 400 | $288.00 | $1.60 | ~$5.00 | **~$294.60** |
| Large team (50 users) | 1,000 | $720.00 | $4.00 | ~$12.00 | **~$736.00** |

## Cost Optimization Recommendations

1. **Transcribe is 96% of cost** — consider batch transcription ($0.024/min vs $0.024/sec for streaming) for non-real-time use cases, or reduce meeting duration captured.

2. **Free tier coverage** — Lambda, Step Functions, Cognito, and DynamoDB are effectively free at this scale. S3 is negligible.

3. **CloudFront** — the 1 TB/month free tier for data transfer covers most small-team usage. Cost only applies beyond that.

4. **Bedrock model choice** — Claude 3 Haiku is already the most cost-effective option. Switching to a larger model (Sonnet/Opus) would increase this 10-50x.

5. **Reserved capacity** — not applicable for serverless services. All services use pay-per-use pricing.

6. **Lifecycle policies** — S3 Glacier transition after 90 days reduces long-term storage costs for old transcripts and reports.

## What Costs Nothing (At Rest)

When the app is deployed but not actively used, the only ongoing costs are:

| Resource | At-Rest Cost |
|----------|-------------|
| S3 storage | ~$0.01/month per GB stored |
| CloudWatch log storage | ~$0.03/month per GB stored |
| CloudFront distribution | $0.00 (no charge when idle) |
| All other services | $0.00 (pay-per-use only) |

The serverless architecture means you pay almost nothing when the app is idle.

## Disclaimer

These estimates are based on published AWS pricing for `ap-northeast-1` as of April 2026 and the usage assumptions stated above. Actual costs may vary based on real usage patterns, data transfer volumes, and AWS pricing changes. Use the [AWS Pricing Calculator](https://calculator.aws/) for more precise estimates based on your specific workload.
