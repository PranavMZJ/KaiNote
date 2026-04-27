# ------------------------------------------------------------------------------
# Step Functions State Machine — Post-Processing Workflow
# Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 13.4, 16.1, 16.2
# ------------------------------------------------------------------------------

# ==============================================================================
# CloudWatch Log Group for Step Functions execution logs
# ==============================================================================

resource "aws_cloudwatch_log_group" "sfn_workflow" {
  name              = "/aws/states/${local.name_prefix}-workflow"
  retention_in_days = 30
  tags              = local.common_tags
}

# ==============================================================================
# Step Functions State Machine — Standard type
# ==============================================================================

resource "aws_sfn_state_machine" "workflow" {
  name     = "${local.name_prefix}-workflow"
  role_arn = aws_iam_role.sfn.arn
  type     = "STANDARD"

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn_workflow.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  definition = jsonencode({
    Comment = "Meeting minutes post-processing workflow"
    StartAt = "LoadTranscript"
    States = {

      # -----------------------------------------------------------------------
      # Step 1: Load raw transcript from S3
      # -----------------------------------------------------------------------
      LoadTranscript = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-cleanup"
        Parameters = {
          "action"      = "load"
          "meetingId.$" = "$.meetingId"
          "userId.$"    = "$.userId"
          "s3Key.$"     = "$.transcriptKey"
        }
        ResultPath = "$.transcript"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "CleanTranscript"
      }

      # -----------------------------------------------------------------------
      # Step 2: Clean and normalize transcript
      # -----------------------------------------------------------------------
      CleanTranscript = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-cleanup"
        Parameters = {
          "action"         = "clean"
          "meetingId.$"    = "$.meetingId"
          "userId.$"       = "$.userId"
          "transcript.$"   = "$.transcript"
        }
        ResultPath = "$.cleanedTranscript"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "CheckTokenCount"
      }

      # -----------------------------------------------------------------------
      # Step 3: Check token count and branch
      # -----------------------------------------------------------------------
      CheckTokenCount = {
        Type = "Choice"
        Choices = [
          {
            Variable              = "$.cleanedTranscript.totalTokenCount"
            NumericGreaterThan    = 10000
            Next                  = "ChunkTranscript"
          }
        ]
        Default = "GenerateMinutes"
      }

      # -----------------------------------------------------------------------
      # Step 4a: Chunk transcript (large transcripts > 10,000 tokens)
      # -----------------------------------------------------------------------
      ChunkTranscript = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-chunker"
        Parameters = {
          "meetingId.$"          = "$.meetingId"
          "userId.$"             = "$.userId"
          "cleanedTranscript.$"  = "$.cleanedTranscript"
        }
        ResultPath = "$.chunks"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "GenerateMinutesChunked"
      }

      # -----------------------------------------------------------------------
      # Step 4b: Generate minutes from chunked transcript (Map state)
      # -----------------------------------------------------------------------
      GenerateMinutesChunked = {
        Type     = "Map"
        ItemsPath = "$.chunks"
        Parameters = {
          "meetingId.$" = "$.meetingId"
          "userId.$"    = "$.userId"
          "chunk.$"     = "$$.Map.Item.Value"
        }
        ResultPath = "$.chunkResults"
        Iterator = {
          StartAt = "GenerateMinutesForChunk"
          States = {
            GenerateMinutesForChunk = {
              Type     = "Task"
              Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-generator"
              Retry = [
                {
                  ErrorEquals = [
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                    "Lambda.TooManyRequestsException"
                  ]
                  IntervalSeconds = 2
                  MaxAttempts     = 2
                  BackoffRate     = 2.0
                  JitterStrategy  = "FULL"
                }
              ]
              End = true
            }
          }
        }
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "MergeResults"
      }

      # -----------------------------------------------------------------------
      # Step 4c: Merge chunked results
      # -----------------------------------------------------------------------
      MergeResults = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-generator"
        Parameters = {
          "action"          = "merge"
          "meetingId.$"     = "$.meetingId"
          "userId.$"        = "$.userId"
          "chunkResults.$"  = "$.chunkResults"
        }
        ResultPath = "$.report"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "ValidateSchema"
      }

      # -----------------------------------------------------------------------
      # Step 4d: Generate minutes (single transcript ≤ 10,000 tokens)
      # -----------------------------------------------------------------------
      GenerateMinutes = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-generator"
        Parameters = {
          "action"              = "generate"
          "meetingId.$"         = "$.meetingId"
          "userId.$"            = "$.userId"
          "cleanedTranscript.$" = "$.cleanedTranscript"
        }
        ResultPath = "$.report"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "ValidateSchema"
      }

      # -----------------------------------------------------------------------
      # Step 5: Validate generated report against Minutes Schema
      # -----------------------------------------------------------------------
      ValidateSchema = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-validator"
        Parameters = {
          "meetingId.$" = "$.meetingId"
          "userId.$"    = "$.userId"
          "report.$"    = "$.report"
        }
        ResultPath = "$.validation"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "CheckValidation"
      }

      # -----------------------------------------------------------------------
      # Step 5b: Check validation result and decide next step
      # -----------------------------------------------------------------------
      CheckValidation = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.validation.isValid"
            BooleanEquals = true
            Next         = "StoreReport"
          },
          {
            And = [
              {
                Variable     = "$.validation.isValid"
                BooleanEquals = false
              },
              {
                Variable           = "$.validation.attemptCount"
                NumericLessThan    = 3
              }
            ]
            Next = "RetryGeneration"
          }
        ]
        Default = "MarkFailed"
      }

      # -----------------------------------------------------------------------
      # Step 5c: Retry generation (increment attempt counter)
      # -----------------------------------------------------------------------
      RetryGeneration = {
        Type = "Pass"
        Parameters = {
          "meetingId.$"         = "$.meetingId"
          "userId.$"            = "$.userId"
          "transcriptKey.$"     = "$.transcriptKey"
          "cleanedTranscript.$" = "$.cleanedTranscript"
          "validation" = {
            "attemptCount.$" = "States.MathAdd($.validation.attemptCount, 1)"
          }
        }
        ResultPath = "$"
        Next       = "GenerateMinutes"
      }

      # -----------------------------------------------------------------------
      # Step 6a: Store validated report to S3
      # -----------------------------------------------------------------------
      StoreReport = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-store"
        Parameters = {
          "meetingId.$" = "$.meetingId"
          "userId.$"    = "$.userId"
          "report.$"    = "$.report"
        }
        ResultPath = "$.storage"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "MarkFailed"
          }
        ]
        Next = "UpdateStatus"
      }

      # -----------------------------------------------------------------------
      # Step 6b: Mark workflow as failed
      # -----------------------------------------------------------------------
      MarkFailed = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-store"
        Parameters = {
          "action"        = "mark_failed"
          "meetingId.$"   = "$.meetingId"
          "userId.$"      = "$.userId"
          "error.$"       = "$.error"
        }
        ResultPath = "$.failureResult"
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.markFailedError"
            Next        = "UpdateStatus"
          }
        ]
        Next = "UpdateStatus"
      }

      # -----------------------------------------------------------------------
      # Step 7: Update meeting status (terminal state)
      # -----------------------------------------------------------------------
      UpdateStatus = {
        Type     = "Task"
        Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-store"
        Parameters = {
          "action"      = "update_status"
          "meetingId.$" = "$.meetingId"
          "userId.$"    = "$.userId"
        }
        Retry = [
          {
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
              "Lambda.TooManyRequestsException"
            ]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2.0
            JitterStrategy  = "FULL"
          }
        ]
        End = true
      }
    }
  })

  tags = local.common_tags
}
