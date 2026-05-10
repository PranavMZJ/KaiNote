# ------------------------------------------------------------------------------
# SNS Topic — Post-Meeting Notifications
# Requirements: Agent 2.1, 6.3, 7.2
# ------------------------------------------------------------------------------

resource "aws_sns_topic" "notifications" {
  name = "${local.name_prefix}-notifications"

  tags = local.common_tags
}

# --- Email subscriptions ---
resource "aws_sns_topic_subscription" "email_1" {
  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = "pranavswaroopmn@gmail.com"
}

resource "aws_sns_topic_subscription" "email_2" {
  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = "pranavgowda91@gmail.com"
}
