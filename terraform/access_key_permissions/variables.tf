variable "username" {
  description = "Name of an existing IAM user to grant permissions to. Looked up by name; not created or owned by this module."
  type        = string
}

variable "policies" {
  description = "ARNs of existing IAM managed policies to attach to the user, e.g. an AWS-managed one such as arn:aws:iam::aws:policy/AdministratorAccess. May be empty if statements is set."
  type        = list(string)
  default     = []
}

variable "statements" {
  description = "IAM policy statements to grant the user, in a managed policy created for the user. May be empty if policies is set. Each statement may have conditions, as in an aws_iam_policy_document. Leaving both empty grants nothing beyond the statements the module always adds: a deny of creating S3 buckets outside the account regional namespace."
  type = list(object({
    effect    = string
    actions   = list(string)
    resources = list(string)
    conditions = optional(list(object({
      test     = string
      variable = string
      values   = list(string)
    })), [])
  }))
  default = []
}
