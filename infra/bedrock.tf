# ------------------------------------------------------------------------------
# Bedrock Guardrail
# ------------------------------------------------------------------------------

resource "aws_bedrock_guardrail" "main" {
  name                      = "${local.name_prefix}-guardrail"
  description               = "Content safety guardrail for meeting minutes generation"
  blocked_input_messaging   = "Your request was blocked by the content safety guardrail."
  blocked_outputs_messaging = "The generated response was blocked by the content safety guardrail."

  # Content filter: block hate, insults, sexual, violence at HIGH threshold
  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
  }

  # Sensitive information filter: mask PII (SSN, credit card numbers)
  sensitive_information_policy_config {
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "US_SOCIAL_SECURITY_NUMBER"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "CREDIT_DEBIT_CARD_NUMBER"
    }
  }

  tags = local.common_tags
}
