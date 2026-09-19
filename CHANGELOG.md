# Changelog

Notable changes will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Will not document changes to agent configuration used in development.

<!--
## [1.0.0] - YYYY-MM-DD

### Added
- New feature description.

### Changed
- Changed feature description.

### Deprecated
- Deprecated feature description.

### Removed
- Removed feature description.

### Fixed
- Bug fix description.

### Security
- Security fix description.

### Documentation
- Documentation change description.

### Tests
- Testing change description.
-->

## [0.0.0-dev.8] (2026-09-18)

### Added
- Added tools for `go` and `claude_sync`. ([#8](https://github.com/fogies/pyfogies/pull/8))

### Changed
- Updated Terraform to require 1.15, gaining support for `const` variables. ([#8](https://github.com/fogies/pyfogies/pull/8))
- Refactored `environ` to consistently expose `raise_if_env_exists`. ([#8](https://github.com/fogies/pyfogies/pull/8))

### Removed
- Removed `__PYFOGIES_VERSION__` from `terraform_templated`. ([#8](https://github.com/fogies/pyfogies/pull/8))

## [0.0.0-dev.7] (2026-09-17)

### Added
- Added consistent support for `tags` variable in Terraform modules. ([#7](https://github.com/fogies/pyfogies/pull/7))
- Added `terraform_templated` with support for `__PYFOGIES_VERSION__`. ([#7](https://github.com/fogies/pyfogies/pull/7))

### Changed
- Refactored tasks to accept context manager factories. ([#7](https://github.com/fogies/pyfogies/pull/7))
- Refactored Terraform tool to resolve relative paths. ([#7](https://github.com/fogies/pyfogies/pull/7))

### Tests
- Refactored testing for Terraform backend. ([#7](https://github.com/fogies/pyfogies/pull/7))

## [0.0.0-dev.6] (2026-09-15)

### Added
- Added Terraform modules for `access_key_permissions`, `alb_dns`, `cloudwatch`, `ecs`, `security_group/alb_public_http_https`, and `security_group/ecs_from_alb_http`. ([#6](https://github.com/fogies/pyfogies/pull/6))
- Added tool and tasks for `aws_access_key`. ([#6](https://github.com/fogies/pyfogies/pull/6))
- Added `ensure_from_template`. ([#6](https://github.com/fogies/pyfogies/pull/6))

### Changed
- Refactored `ready_poll`. ([#6](https://github.com/fogies/pyfogies/pull/6))
- Refactored `aws_environ_from_config` and `aws_environ_from_profile`. ([#6](https://github.com/fogies/pyfogies/pull/6))

### Tests
- Refactored self-signed ALB into a shared fixture. ([#6](https://github.com/fogies/pyfogies/pull/6))
- Extended testing for Terraform modules. ([#6](https://github.com/fogies/pyfogies/pull/6))

## [0.0.0-dev.5] (2026-08-11)

### Added
- Added Terraform modules for `alb`, `backend`, `ecr`, `hosted_zone`, `network`. ([#5](https://github.com/fogies/pyfogies/pull/5))
- Added tools and tasks for `terraform` and related `terraform_backend`. ([#5](https://github.com/fogies/pyfogies/pull/5))
- Added tool for `aws_environ`. ([#5](https://github.com/fogies/pyfogies/pull/5))
- Added templates for `secrets/aws.toml`, `secrets/poetry.toml`, `secrets/pyfogies-tests.toml`. ([#5](https://github.com/fogies/pyfogies/pull/5))

### Changed
- Improved task for `format`. ([#5](https://github.com/fogies/pyfogies/pull/5))
- Improved tool for `command`. ([#5](https://github.com/fogies/pyfogies/pull/5))

### Tests
- Refactored tests ([#5](https://github.com/fogies/pyfogies/pull/5)).
- Extended testing for Terraform modules. ([#5](https://github.com/fogies/pyfogies/pull/5))

## [0.0.0-dev.4] (2026-04-14)

### Added
- Added `py.typed` marker for typed distribution. ([#4](https://github.com/fogies/pyfogies/pull/4))

## [0.0.0-dev.3] (2026-03-24)

### Fixed
- Fixed shadowing caused by `paths.py`. ([#3](https://github.com/fogies/pyfogies/pull/3))

## [0.0.0-dev.2] (2026-03-20)

### Added
- Added tools for `aws_environ`, `command`, `environ`, `ollama`, `terraform`. ([#2](https://github.com/fogies/pyfogies/pull/2))
- Added Terraform module for `backend`. ([#2](https://github.com/fogies/pyfogies/pull/2)).

### Tests
- Added testing for Terraform modules. ([#2](https://github.com/fogies/pyfogies/pull/2))
- Extended testing of tools. ([#2](https://github.com/fogies/pyfogies/pull/2)).

## [0.0.0-dev.1] (2025-12-23)

### Added
- Added tasks for `format`, `lint`, `poetry`, `test`. ([#1](https://github.com/fogies/pyfogies/pull/1))

### Tests
- Added testing for tool availability. ([#1](https://github.com/fogies/pyfogies/pull/1))
