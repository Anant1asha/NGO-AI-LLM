# Releasing Hachi to PyPI

## One-Time Setup

### 1. Create the PyPI Project

1. Go to [pypi.org](https://pypi.org) and sign in (or create an account).
2. Click **"Create project"** and name it `hachi-og`.
3. Once created, go to the project's settings page.

### 2. Add GitHub as a Trusted Publisher

On the PyPI project page:

1. Navigate to **Settings** → **Publishing**.
2. Click **"Add a new pending publisher"**.
3. Fill in:
   - **GitHub repository name**: `OpenGigantic/hachi`
   - **GitHub workflow name**: `release.yml`
   - **GitHub environment name**: `pypi`

4. Click **Create** and verify the pending entry appears.

### 3. Create the GitHub Environment

In the [OpenGigantic/hachi](https://github.com/OpenGigantic/hachi) repository:

1. Go to **Settings** → **Environments** (under Code and automation).
2. Click **New environment**.
3. Name it `pypi` (exactly).
4. Click **Configure environment**.
5. Leave all rules blank (no IP allowlist / required reviewers needed).
6. Click **Save protection rules**.

## Publishing a Release

1. **Update `pyproject.toml`** — bump the version (e.g., `0.1.0` → `0.2.0`).

2. **Commit and tag**:
   ```bash
   git add pyproject.toml
   git commit -m "chore: bump version to 0.2.0"
   git tag v0.2.0
   git push origin main --tags
   ```

   The workflow triggers automatically on the tag. Alternatively, go to GitHub, create a [Release](https://github.com/OpenGigantic/hachi/releases) for the tag, and the workflow runs there too.

3. **Monitor the workflow** at [Actions](https://github.com/OpenGigantic/hachi/actions) → **Release**.

4. **Verify on PyPI** — within seconds, the new version appears at [pypi.org/project/hachi-og](https://pypi.org/project/hachi-og).

Users can now install:
```bash
pipx install hachi-og
uv tool install hachi-og
```

## Troubleshooting

- **Trusted Publisher not recognized**: Go back to PyPI project Settings → Publishing and confirm the pending entry is there. If it shows "active", GitHub is already wired.
- **Workflow fails with auth error**: Double-check the `pypi` environment exists and the GitHub repo in the PyPI Trusted Publisher matches exactly (`OpenGigantic/hachi`).
- **Version mismatch**: The workflow checks that the git tag (`v0.2.0`) matches `pyproject.toml` (`0.2.0`). Tag must be `v<version>`.

---

Once this is done, you'll never need an API token. The workflow uses **OIDC** (OpenID Connect) to prove "this job is from GitHub" and PyPI trusts it automatically.
