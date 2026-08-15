resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.project}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 3
  dimensions          = { FunctionName = aws_lambda_function.app.function_name }
  alarm_actions       = []
}