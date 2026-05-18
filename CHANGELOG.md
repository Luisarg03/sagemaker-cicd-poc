# Changelog

## v1.0.0 — 2026-05-18

### Added
- GHAS full stack: CodeQL, Dependabot, Dependency Review, Secret Scanning, Push Protection
- Immutable artifact promotion flow DEV → QA → PROD using local Docker registry (`registry:2`)
- `scripts/update_config.py`: CLI for environment-aware config hydration before deploy
- `publish-to-registry` job: builds and pushes images with `sha-{github.sha}` tags
- `promote-to-qa` and `promote-to-prod` jobs: `docker tag/push` only — no rebuild
- `deploy-pipeline` job: hydrates `config.json` per environment before `pipeline.upsert()`

### Changed
- Docker images tagged as `sha-{commit}` — never `:latest`
- Registry simulates Artifactory (`registry:2` on port 5001)

### Security
- CodeQL analysis on every PR (Advanced setup)
- Secret scanning + push protection enabled
- Dependency Review blocks PRs with HIGH+ vulnerabilities
