# Storage package feasibility investigation

Update, November 17: Team 1 supplied a new standalone package at `784be97`.
Its joint installation findings are in [Team 1 integration progress](HW3_STORAGE_TEAM1_INTEGRATION.md).
The service-revision `6567b26` limitations below are historical; they do not
describe that new package. Workflow selection and real swap remain pending.

Owner: Kristie (Member 4). Investigated November 16, 2026, at application
baseline `f7c59d1`, with Codex assistance. This is task 3's research record;
it changes no application code, dependencies, lockfile, or credentials.
Subsequently, Hari confirmed that adding the provider package as a dependency
is mandatory (reported by Kristie). The active direction is package integration;
see the [transition plan](HW3_STORAGE_PACKAGE_TRANSITION.md). No Dropbox
operations, provider endpoint requests, or login occurred in this investigation.

## Findings

| Question | Team 3 | Team 1 |
| --- | --- | --- |
| Inspected revision | `fde60d4fb648df6defb918ff815fe940c525adc7` (`hw2`) | `6567b262559df46c85371182573cc1242b17c031` (`hw2-milestone3`) |
| External installation | Passed with explicit dependencies and `--no-sources` | Fallback build/install passed with `--no-deps`; usable standalone runtime not established |
| Distribution / import | `dropbox-client-impl==0.1.0` / `dropbox_client_impl` | Auto-generated `app==0.0.0` / `app` |
| Shared interface | `DropboxDocumentStorage` subclasses official `DocumentStorage` | Local `DocumentStorage` protocol uses `upload`, not official `create` |
| Python | Declares >=3.12; install/import probed on 3.14.8 | No Requires-Python metadata; tooling targets 3.12; fallback install used 3.12.1 |
| Ready for configuration-only package swap? | Candidate, pending real credentials, integration and provider verification | Requires packaging/namespace and contract alignment before claiming interchangeability |

These are findings about the pinned revisions, not claims about every branch or
future release. HTTP endpoint access permission does not supply credentials for
running either implementation inside Team 5's process.

## Team 3: reproducible installation and import

The implementation is a nested distribution, not the repository-root service.
Install it together with its internal client interface and the official shared
contract. In a disposable consumer environment, the following succeeded:

```powershell
uv venv --python 3.14 .venv
uv pip install --no-sources --python .venv/Scripts/python.exe `
  "dropbox-client-impl @ git+https://github.com/Shreyas191/OSPSD-Team-3.git@fde60d4fb648df6defb918ff815fe940c525adc7#subdirectory=src/dropbox_client_impl" `
  "cloud-storage-client-api @ git+https://github.com/Shreyas191/OSPSD-Team-3.git@fde60d4fb648df6defb918ff815fe940c525adc7#subdirectory=src/cloud_storage_client_api" `
  "cloud-storage-api @ git+https://github.com/Dayana20/ospsd26-cloud-storage@0.3.1#subdirectory=src/cloud_storage_api"
```

The actual disposable environment was named `consumer`; `.venv` above is an
operator-friendly equivalent. The application environment was not modified.
Without `--no-sources`, the explicit install failed with conflicting URLs for
`cloud-storage-api`, including after matching the `.git` spelling. The provider's
uv source/workspace configuration is not a portable consumer recipe here.
`--no-sources` plus all three direct requirements resolved and built successfully;
it is not a proposal to change this application's dependency policy globally.

Follow-up: task 2 successfully uses root project `[tool.uv.sources]` entries for
both Team 3 packages, so the application's normal `uv sync --frozen` works
without `--no-sources`. The command above remains the historical isolated pip
experiment, not the application setup command. See
[dependency installation progress](HW3_STORAGE_PACKAGE_TRANSITION.md#dependency-installation-progress).

Installed provenance from distribution `direct_url.json`:

- Both Team 3 distributions: full commit `fde60d4fb648df6defb918ff815fe940c525adc7`.
- Shared contract: tag `0.3.1` resolved to
  `664afc92f7cc0b2ee51cde6ddfa088cc3b37206c`. Its installed distribution version
  is **0.2.0**. Git tag and package metadata version are different; record both.
- Resolved SDK: `dropbox==12.2.5`. The disposable install is not a locked production
  environment; a later integration must record its own resolved dependencies.

The import is:

```python
from cloud_storage_api import DocumentStorage
from dropbox_client_impl import DropboxDocumentStorage
```

An offline probe disabled dotenv loading, removed inherited `DROPBOX_*` values,
set the token-file location to an absent scratch file, and blocked socket
connection/DNS functions before import. It verified:

- Import succeeds even when the consumer already owns an `app` module.
- `DropboxDocumentStorage(client=object())` constructs, has no abstract methods,
  and is an instance of the installed official `DocumentStorage`.
- Default construction without credentials raises `DropboxAuthError`.

The injected object only checks construction/interface identity; no method was
called on it. This does not establish CRUD correctness, full conformance,
compatibility with the complete Team 5 dependency set, or a real workflow.

The existing Team 3 `v0.2.0` tag resolves to
`3411cdf8d5723a6ebda3e6799ab3e1384819767f`; its tree does not contain this
`document_storage.py` wrapper. Therefore the earlier HTTP release citation
cannot be reused as package-import evidence. John subsequently approved
`fde60d4` as the current pin and confirmed the explicit-dependency/`--no-sources`
consumer installation approach. A wrapper release tag is still unavailable.

## Initialization and credential boundaries

Team 3's default constructor creates a `DropboxClient`. Source inspection says
client construction checks configuration without contacting Dropbox; the
credential-free probe confirms the missing-configuration path only.
Credential resolution is refresh token first (environment or token file), with
`DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET`; `DROPBOX_ACCESS_TOKEN` is the fallback.
`DROPBOX_TOKEN_FILE` overrides the default `.dropbox_token.json` location.
The auth module calls `load_dotenv()` on import. A future integration must make
configuration ownership and credential-file location explicit rather than
accidentally relying on another project's working directory.

Constructor `DropboxAuthError` is outside the shared operation-error boundary.
Translate missing/invalid local configuration at dependency construction before
issue/event creation; do not let a raw initialization error reach the workflow.
This is an implementation requirement for a later package task, not completed
behavior. Runtime operation uncertainty must still follow the
[failure policy](HW3_STORAGE_FAILURE_POLICY.md).

Team 1's factory `app.dependencies.get_document_storage()` constructs
`DropboxStorage`, optionally wraps it in a Redis-backed cache, and uses globally
loaded settings/cached factories. Its Dropbox client also accepts refresh token
plus app key/secret, or an access-token fallback. No Team 1 factory was executed.
Real token setup, scopes, account authorization and provider checks are task 4
or later work; no secret values belong in this record.

## Team 1: installable archive is not yet a consumer package

At the inspected revision, `pyproject.toml` contains tooling settings but no
`[project]` or `[build-system]`; there is no `setup.py` or `setup.cfg`.
`uv pip install --dry-run --no-deps` warned that this did not appear to be a
Python project, but fallback packaging still succeeded. A separate scratch
`--target` installation with `--no-deps` produced `app==0.0.0` containing
`app/providers/base.py`. Installed metadata has neither `Requires-Dist` nor
`Requires-Python`. This is not an installation-failure claim.

The problems for this consumer are:

- Team 5 already imports its own `app`. Adding another provider's `app` creates
  an import collision; copying source or changing `sys.path` is not a reliable
  configuration-only package swap.
- Runtime dependencies are in `requirements.txt`, not distribution metadata.
  Installing that entire service requirements file into Team 5 is not a verified
  or approved resolution. It pins the shared contract to Git tag `0.2.0`, while
  this application uses tag `0.3.1`; compatibility needs validation.
- The local protocol returns `FileResource` and exposes `upload(path, content)`
  rather than the official `create(path, content)` boundary. Other methods and
  metadata types also need comparison; changing an import alone is insufficient.

Request a supported installable distribution with a provider-specific namespace,
declared runtime dependencies/Python support, a documented construction API and
official `DocumentStorage` compatibility. If Team 1 proposes a different branch
or a shim, investigate and agree ownership before implementing it. No provider
code was modified or vendored during this research.

## Follow-up after the TA decision

Package integration is required. Proceed with Team 3's approved pin without
waiting for Team 1. Implement reproducible project dependencies, construction
error mapping and workflow wiring in separate small commits. Keep
`DocumentSummaryStore` depending on the shared contract. Team 1's supported
package/contract solution is still needed before a configuration-only swap can
be implemented and verified. See the transition plan for ownership and checks.

The unresolved Team 1 boundary prevents claiming a complete package swap now.
The Team 3 install/import blocker is narrowed, not proof of milestone completion.

## Pinned sources

- [Team 3 implementation and package](https://github.com/Shreyas191/OSPSD-Team-3/tree/fde60d4fb648df6defb918ff815fe940c525adc7/src/dropbox_client_impl)
- [Team 3 client interface package](https://github.com/Shreyas191/OSPSD-Team-3/tree/fde60d4fb648df6defb918ff815fe940c525adc7/src/cloud_storage_client_api)
- [Team 3 historical release tree](https://github.com/Shreyas191/OSPSD-Team-3/tree/3411cdf8d5723a6ebda3e6799ab3e1384819767f)
- [Shared contract source at resolved tag](https://github.com/Dayana20/ospsd26-cloud-storage/tree/664afc92f7cc0b2ee51cde6ddfa088cc3b37206c/src/cloud_storage_api)
- [Team 1 source and packaging](https://github.com/Dayana20/sandbox/tree/6567b262559df46c85371182573cc1242b17c031)
- [Team 1 local storage protocol](https://github.com/Dayana20/sandbox/blob/6567b262559df46c85371182573cc1242b17c031/app/providers/base.py)
- [Team 1 construction](https://github.com/Dayana20/sandbox/blob/6567b262559df46c85371182573cc1242b17c031/app/dependencies.py)
