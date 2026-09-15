output "username" {
  description = "Name of the IAM user granted permissions."
  value       = data.aws_iam_user.user.user_name
}

output "policy_name" {
  description = "Name of the inline policy attached to the user."
  value       = aws_iam_user_policy.permissions.name
}

output "policy_json" {
  description = "The actual IAM policy document attached to the user."
  value       = aws_iam_user_policy.permissions.policy
}
