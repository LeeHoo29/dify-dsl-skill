# Changelog

## 0.2.6 - 2026-09-23

- Added dependency-by-mode documentation for Skill installation, DSL authoring, and local Dify synchronization.
- Added host preflight commands and a natural-language environment check prompt.
- Clarified that the Skill does not install Dify and that container Python is provided by the running Dify API service.

## 0.2.5 - 2026-09-23

- Added a redacted live local Dify canvas crop to the final stage of the 30-second demo GIF.
- Kept account/sidebar content out of the public visual asset while preserving the published workflow evidence.

## 0.2.4 - 2026-09-23

- Fixed the portable plugin manifest version so it matches the compatibility manifest.

## 0.2.3 - 2026-09-23

- Added a 30-second, README-ready GIF showing natural-language authoring, Code-source synchronization, ELK layout, validation, and local Draft/Published verification.
- Added the deterministic `scripts/create_demo_gif.py` renderer and Pillow dependency for future revisions.

## 0.2.2 - 2026-09-23

- Added copyable natural-language installation prompts for the three Skills and the authoring-only pair.
- Clarified that installation does not configure Dify or authorize import/publication.
- Documented the Dify 1.17.1 tested baseline and the required dry-run step for other versions.

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
