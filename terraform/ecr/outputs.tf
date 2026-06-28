data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

output "registry_url" {
  description = "URL of the ECR registry (account and region scoped)."
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com"
}

output "repositories" {
  description = "Map of repository name to repository details."
  value = tomap({
    for name, repository in aws_ecr_repository.repository : name => {
      name           = name
      arn            = repository.arn
      repository_url = repository.repository_url
    }
  })
}
