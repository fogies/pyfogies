variable "name" {
  description = "Name for the security group."
  type        = string
}

variable "vpc_id" {
  description = "VPC in which to create the security group."
  type        = string
}

variable "alb_security_group_id" {
  description = "ID of the ALB security group. Inbound traffic on container_port is allowed only from this group."
  type        = string
}

variable "container_port" {
  description = "Port the ECS container listens on."
  type        = number
  default     = 80
}

variable "tags" {
  description = "Tags to apply to the security group."
  type        = map(string)
  default     = {}
}
