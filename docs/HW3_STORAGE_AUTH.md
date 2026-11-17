# Team 5 Dropbox authorization and package probe

Owner: Kristie (Member 4), with Codex assistance. Juno approved Team5-Review
reuse. This is preparation, not evidence of OAuth, live CRUD or workflow success.

## App and account

Reuse Team5-Review (Scoped App / App Folder). Confirm the intended Dropbox
account with Juno and select it during authorization: the app does not select
the account. If another account cannot link because development users are
restricted to the owner, coordinate access with Juno.

Existing settings match the provider: redirect URI
`http://localhost:8080/oauth/callback` (no `.4` suffix), with scopes
`account_info.read`, `files.metadata.read`, `files.metadata.write`,
`files.content.read`, `files.content.write`. No app-setting change is needed.
Team 3's account, app secrets and tokens are not used.

## Local PowerShell setup

Operator commands below have not been executed as part of this commit. Run in
a local interactive terminal; keep secrets out of git, chat, Slack and evidence.

```powershell
Set-Location 'C:\Users\이채린\Desktop\NYU\4-1\OpenSourceProgramming\OSPSD-Team-5'
uv sync --frozen
$dropboxCredentialDir = Join-Path $env:LOCALAPPDATA 'OSPSD-Team5\Dropbox'
New-Item -ItemType Directory -Force -Path $dropboxCredentialDir | Out-Null
$env:DROPBOX_TOKEN_FILE = Join-Path $dropboxCredentialDir 'refresh-token.json'
$env:DROPBOX_REDIRECT_URI = 'http://localhost:8080/oauth/callback'
$env:PYTHON_DOTENV_DISABLED = '1'
$env:STORAGE_ROOT_PATH = '/ospsd-team5-hw3'
$env:DROPBOX_APP_KEY = Read-Host 'Team5-Review App key'
$dropboxSecretInput = Read-Host 'Team5-Review App secret' -AsSecureString
$env:DROPBOX_APP_SECRET = [System.Net.NetworkCredential]::new('', $dropboxSecretInput).Password
Remove-Variable dropboxSecretInput
Remove-Item Env:DROPBOX_REFRESH_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:DROPBOX_ACCESS_TOKEN -ErrorAction SilentlyContinue
```

These variables belong to this terminal session; supply them again in a new
session and run the server/probe from the configured terminal. Do not overwrite
the project's existing `.env`. `PYTHON_DOTENV_DISABLED=1` prevents implicit
provider dotenv loading. An environment refresh token takes precedence over the
file, so stale overrides are removed above for file-based login. The token file
is outside the checkout; never display its contents.

## OAuth login and authentication check

If the selected token file already contains credentials that must be retained,
choose a different absolute token-file path before login, which writes the file.

```powershell
.\.venv\Scripts\python.exe -m dropbox_client_impl login
```

Confirm the intended account in the browser and approve access. If the browser
does not open, open the printed authorization URL while the command runs. Local
port 8080 must be available for the callback listener. Finish within five minutes.
Expected output includes saved credentials and `Dropbox authentication OK: ...`.

```powershell
Test-Path -LiteralPath $env:DROPBOX_TOKEN_FILE
.\.venv\Scripts\python.exe -m dropbox_client_impl
```

Expect `True` and a successful account check. Login and the second command
contact Dropbox; neither proves file CRUD. Report success/failure without token
values or personal account details. No manual access-token generation is needed.

## Test folder and opt-in package probe

In the authorized account's Dropbox web UI, locate the app-specific Team5-Review
folder and create/confirm its `ospsd-team5-hw3` child folder. The API path is
`/ospsd-team5-hw3`, relative to the app root, not `/Apps/Team5-Review/...`.
Team 3's test folder is on a different account. The probe neither creates nor
deletes the configured root folder.

Run this only after authorization/folder preparation (task 7). It creates and
deletes one UUID-named Markdown file, checking health, initial absence, UTF-8
upload/readback, duplicate-create conflict, unchanged bytes and final absence.
It uses the Team 3 package and the workflow's scoped SDK construction; no HTTP
endpoint URL is needed. The generic summary byte verification is shared;
production's package-specific failure classifier remains in its summary store.

```powershell
$storageEvidenceName = 'HW3_STORAGE_TEAM3_PACKAGE_' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json'
$storageEvidencePath = Join-Path 'docs\evidence' $storageEvidenceName
.\.venv\Scripts\python.exe -m scripts.verify_storage_live --execute --output $storageEvidencePath
$LASTEXITCODE
```

Exit code `0` requires `result=passed`; confirm `cleanup=confirmed absent` in
the JSON. Existing output files are refused before remote work. Evidence records
application HEAD, current source/lockfile hashes, Python and installed package
versions/Git provenance. HEAD alone does not establish a clean working tree.
Credential values and raw provider error messages are not recorded.

If cleanup fails, inspect only that run's exact UUID path and coordinate manual
cleanup before claiming success. Never delete the entire folder or another
run's file. Unlike production recovery, the probe may clean its own scratch
file after an uncertain write: see the [failure policy](HW3_STORAGE_FAILURE_POLICY.md).

Immediate cleanup does not establish independent inspection of stored contents.
Arrange a separate full-workflow run with an authorized Team 5 teammate to inspect
the retained summary and confirm cleanup. The probe leaves direct inspection
`pending` and deployed composed workflow `not exercised`. Preserve the existing
historical HTTP evidence; this commit adds no live evidence.

Provider reference: [Team 3 README at the approved pin](https://github.com/Shreyas191/OSPSD-Team-3/blob/fde60d4fb648df6defb918ff815fe940c525adc7/src/dropbox_client_impl/README.md).
