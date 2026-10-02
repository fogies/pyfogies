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
  description = "IAM policy statements to grant the user as an inline policy. May be empty if policies is set. Leaving both empty grants nothing."
  type = list(object({
    effect    = string
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}
