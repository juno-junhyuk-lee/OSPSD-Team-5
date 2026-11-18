"""Explicit interactive OAuth setup for the consumer's own Google account."""

import argparse
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]

from .authorization import SCOPES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-secrets", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    if args.token_file.exists():
        print(
            "Token file already exists. Remove an obsolete grant deliberately before reauthorizing."
        )
        return 1
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(args.client_secrets), SCOPES
        )
        credentials = flow.run_local_server(
            port=0, timeout_seconds=300, authorization_prompt_message=""
        )
        if not credentials.has_scopes(SCOPES):
            print("Required Calendar event access was not granted.")
            return 1
        # Do not overwrite another grant; remove an obsolete token deliberately first.
        descriptor = os.open(
            args.token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(credentials.to_json())
    except Exception:
        print(
            "Authorization failed. Check the OAuth client, test-user access, and token destination."
        )
        return 1
    print("Authorization saved. Keep the token private and outside your repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
