# ------------------------------------------------------------------------------
# Amazon Cognito User Pool and App Client
# Requirements: 1.1, 1.2, 16.1, 16.2
# ------------------------------------------------------------------------------

resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-user-pool"

  # Self-registration enabled
  auto_verified_attributes = ["email"]

  # Password policy: min 8 chars, require uppercase/lowercase/number/symbol
  password_policy {
    minimum_length                   = 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # Standard attributes
  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  schema {
    name                = "name"
    attribute_data_type = "String"
    required            = false
    mutable             = true

    string_attribute_constraints {
      min_length = 0
      max_length = 256
    }
  }

  # Email verification
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  # Account recovery via email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = local.common_tags
}

resource "aws_cognito_user_pool_client" "main" {
  name         = "${local.name_prefix}-app-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # No client secret for public frontend app
  generate_secret = false

  # Explicit auth flows for frontend usage
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
  ]

  # Token expiry: access token 1 hour, refresh token 30 days
  access_token_validity  = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    refresh_token = "days"
  }

  # Prevent token revocation issues
  prevent_user_existence_errors = "ENABLED"
}
