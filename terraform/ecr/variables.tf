variable "region" {
  description = "AWS region in which to create ECR resources."
  type        = string
}

variable "repositories" {
  description = "Names of ECR repositories to create."
  type        = set(string)
}

variable "force_delete" {
  description = "Whether to force delete repositories even if they contain images."
  type        = bool
}

variable "lifecycle_keep_count_limit" {
  description = "Limit on number of images kept per repository."
  type        = number
}

variable "lifecycle_keep_days_limit" {
  description = "Limit on age of images kept per repository."
  type        = number
}

variable "tags" {
  description = "Tags to apply to ECR resources."
  type        = map(string)
  default     = {}
}
