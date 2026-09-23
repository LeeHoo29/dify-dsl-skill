# Changelog

## 0.2.1 - 2026-09-23

- Fixed Python 3.10 compatibility in local sync scripts by using `timezone.utc` instead of `datetime.UTC`.

## 0.2.0 - 2026-09-23

- Added the `dify-local-sync` Skill for explicitly authorized local self-hosted Dify configuration, import, overwrite, publication, and verification.
- Added safe Inner API setup with generated secrets, tracked-file refusal, mode-600 backups, a managed Compose override, API-only recreation, verification, and rollback.
- Added separate DSL-project and Dify-deployment roots, container-only Inner API create/export, Service Layer overwrite/confirmation/publication, account/workspace membership checks, environment Profile application, local file-to-App mapping, and strict Draft/Published verification.

## 0.1.0 - 2026-09-22

- Initial public release candidate.
- Added Dify DSL and Python Code-node companion skills.
- Added App DSL 0.7.0 validation, portable-secret checks, canonical Code-source synchronization, and ELK automatic layout.
- Added CI coverage for Python 3.10, 3.12, and 3.13 plus Dify 1.17.1 official fixtures.
