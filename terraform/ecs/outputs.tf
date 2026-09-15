output "cluster_arn" {
  description = "ARN of the ECS cluster."
  value       = aws_ecs_cluster.cluster.arn
}

output "service_name" {
  description = "Name of the ECS service."
  value       = aws_ecs_service.service.name
}

output "task_definition_arn" {
  description = "ARN of the ECS task definition (includes revision)."
  value       = aws_ecs_task_definition.task.arn
}

output "target_group_arn" {
  description = "ARN of the ALB target group."
  value       = aws_lb_target_group.target_group.arn
}
