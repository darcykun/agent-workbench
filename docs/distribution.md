# Distribution gates

The current artifact is a Python wheel and source distribution. CI uploads build
artifacts, not packages. GitHub Packages does not offer a PyPI registry. A CLI wheel
belongs on PyPI if its name is available and the maintainer owns the project.

Before adding an actual PyPI upload job: approve the license and version; check package
name availability/ownership; install the built wheel in isolation; approve the exact
release; configure a protected `release` environment with a required reviewer; configure
PyPI trusted publishing; then use the official PyPA publish action pinned to a reviewed
SHA with job-scoped `id-token: write`. No long-lived publishing token is needed.

The manual release-candidate workflow checks for LICENSE and builds artifacts. It
intentionally has no registry upload permission until those prerequisites are satisfied.
Do not convert every push into a package release. GHCR is deferred until a real API
service exists, has container smoke tests, an SBOM and provenance. No empty container
is supplied simply to populate the Packages tab.
