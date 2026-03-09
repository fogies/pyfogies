resource "aws_dynamodb_table" "lock" {
  name         = "${var.name}-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = merge(
    {
      Name = "${var.name}-lock"
    },
    var.tags,
  )
}

