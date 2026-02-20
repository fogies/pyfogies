resource "aws_dynamodb_table" "lock" {
  name         = "${var.name_prefix}-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = merge(
    {
      Name = "${var.name_prefix}-lock"
    },
    var.tags,
  )
}

