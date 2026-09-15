variable "username" {
  description = "Name of an existing IAM user to grant permissions to. Looked up by name; not created or owned by this module."
  type        = string
}

variable "name" {
  description = "Distinguishes this grant from others attached to the same user (e.g. \"backend\", \"network\"), so multiple grants can coexist."
  type        = string
}

variable "statements" {
  description = "IAM policy statements to grant the user."
  type = list(object({
    effect    = string
    actions   = list(string)
    resources = list(string)
  }))
}
