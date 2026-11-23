#!/usr/bin/env python3
"""
Change passwords on Delinea Secret Server secrets via the REST API
(POST /api/v1/secrets/{id}/change-password), which runs Remote Password
Changing (RPC) so the password is changed on the target account too.

Usage examples:
    # Dry run (default): shows what would be called, changes nothing
    python delinea_update_password.py --ids 101 102 103

    # Actually run, letting the secret's password changer generate the password
    python delinea_update_password.py --ids 101 102 --execute

    # Trigger RPC with a generated password via the expire endpoint instead
    python delinea_update_password.py --ids 101 102 --execute --expire

    # Use a specific new password from an env var (single secret)
    python delinea_update_password.py --ids 101 --execute --new-password-env NEW_SECRET_PW

    # Vault only: store a known password in the secret WITHOUT running RPC
    # (the target account is NOT changed; use when the password was already changed elsewhere)
    python delinea_update_password.py --ids 101 --execute --vault-only --new-password-env NEW_SECRET_PW

    # IDs from a file (one per line, '#' comments allowed), with an audit comment,
    # then heartbeat and wait for the result
    python delinea_update_password.py --ids-file ids.txt --execute --comment "CHG0012345 rotation" --verify

Environment variables (nothing is hardcoded):
    SS_BASE_URL   e.g. https://secretserver.example.com/SecretServer
    SS_USERNAME   API user
    SS_PASSWORD   API user's password
    SS_DOMAIN     (optional) domain for AD users
    SS_OTP        (optional) one-time code if the API user requires 2FA (sent as the OTP header)
    SS_VERIFY_TLS (optional) set to "false" to skip TLS verification (not recommended)

Notes:
    * A successful HTTP response only means the request was ACCEPTED. RPC can run
      asynchronously; use --verify to heartbeat and check lastHeartBeatStatus.
    * A timed-out request is reported as UNKNOWN (the change may still have run).
      Check those secrets before re-running them.
    * Confirm the endpoint schemas against your instance's Swagger page
      (<SS_BASE_URL>/swagger) - parameters can differ between versions.

Requirements: pip install requests
"""

import argparse
import os
import sys
import time

import requests
import urllib3


class SecretServer:
    """Thin client: one Session, bearer token, automatic re-auth on 401."""

    def __init__(self, base_url: str, verify: bool):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = verify
        self.token = None

    def authenticate(self) -> None:
        data = {
            "grant_type": "password",
            "username": os.environ["SS_USERNAME"],
            "password": os.environ["SS_PASSWORD"],
        }
        if os.environ.get("SS_DOMAIN"):
            data["domain"] = os.environ["SS_DOMAIN"]
        headers = {}
        if os.environ.get("SS_OTP"):
            headers["OTP"] = os.environ["SS_OTP"]

        resp = self.session.post(f"{self.base_url}/oauth2/token", data=data,
                                 headers=headers, timeout=30)
        if not resp.ok:
            try:
                err = resp.json()
                detail = err.get("error_description") or err.get("error") or resp.text[:300]
            except ValueError:
                detail = resp.text[:300]
            raise RuntimeError(f"Authentication failed: HTTP {resp.status_code} {detail}")
        self.token = resp.json()["access_token"]

    def request(self, method: str, path: str, retries: int = 3, **kwargs) -> requests.Response:
        """Authenticated request. Re-authenticates once on 401, backs off on 429/5xx."""
        if self.token is None:
            self.authenticate()
        kwargs.setdefault("timeout", 120)
        reauthed = False
        attempt = 0
        while True:
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["Authorization"] = f"Bearer {self.token}"
            resp = self.session.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
            kwargs["headers"] = {k: v for k, v in headers.items() if k != "Authorization"}

            if resp.status_code == 401 and not reauthed:
                self.authenticate()
                reauthed = True
                continue
            if resp.status_code in (429, 502, 503, 504) and attempt < retries:
                attempt += 1
                retry_after = resp.headers.get("Retry-After", "")
                time.sleep(int(retry_after) if retry_after.isdigit() else 2 ** attempt)
                continue
            return resp


def change_password(ss: SecretServer, secret_id: int, new_password=None, comment=None,
                    expire=False, vault_only=False, field_slug="password") -> requests.Response:
    """Trigger a password change for one secret. Returns the Response."""
    if vault_only:
        # Writes the value into the vault only; RPC is not run and the target is not changed.
        # NOTE: confirm the body shape for this endpoint in Swagger for your version.
        params = {"autoComment": comment} if comment else None
        return ss.request("PUT", f"/api/v1/secrets/{secret_id}/fields/{field_slug}",
                          params=params, json={"value": new_password})

    if expire:
        # Expiring the secret schedules RPC with a generated password.
        return ss.request("POST", f"/api/v1/secrets/{secret_id}/expire")

    body = {}
    if new_password:
        body["newPassword"] = new_password
    if comment:
        body["comment"] = comment

    # NOTE: confirm in Swagger that this endpoint honours these query parameters.
    params = {"autoCheckout": "true", "autoCheckIn": "true"}
    if comment:
        params["autoComment"] = comment

    return ss.request("POST", f"/api/v1/secrets/{secret_id}/change-password",
                      params=params, json=body)


def verify_secret(ss: SecretServer, secret_id: int, timeout: int, interval: int = 5) -> str:
    """Run a heartbeat, then poll the secret until lastHeartBeatStatus settles.

    Returns the final status string (e.g. 'Success', 'Failed') or a note.
    Caveat: a stale status from an earlier heartbeat can be seen before the new
    one starts; the initial pause reduces (but does not eliminate) that.
    """
    hb = ss.request("POST", f"/api/v1/secrets/{secret_id}/heartbeat")
    if not hb.ok:
        return f"heartbeat request failed: HTTP {hb.status_code} {hb.text[:200]}"

    deadline = time.time() + timeout
    status = "unknown"
    time.sleep(min(interval, timeout))
    while True:
        r = ss.request("GET", f"/api/v1/secrets/{secret_id}", params={"noAutoCheckout": "true"})
        if r.ok:
            status = str(r.json().get("lastHeartBeatStatus", "unknown"))
            if status.lower() not in ("pending", "processing", "unknown"):
                return status
        else:
            status = f"status lookup failed: HTTP {r.status_code}"
        if time.time() >= deadline:
            return f"{status} (still not settled after {timeout}s)"
        time.sleep(interval)


def load_ids(args) -> list[int]:
    ids = list(args.ids or [])
    if args.ids_file:
        with open(args.ids_file, encoding="utf-8-sig") as f:
            for lineno, raw in enumerate(f, 1):
                line = raw.split("#", 1)[0].strip()  # strip comments, incl. inline/indented
                if not line:
                    continue
                try:
                    ids.append(int(line))
                except ValueError:
                    raise SystemExit(f"{args.ids_file}:{lineno}: not a valid secret ID: {raw.strip()!r}")
    return list(dict.fromkeys(ids))  # de-duplicate, keep order


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ids", nargs="*", type=int, help="Secret IDs")
    p.add_argument("--ids-file", help="File with one secret ID per line ('#' comments allowed)")
    p.add_argument("--execute", action="store_true", help="Actually change passwords (default is dry run)")
    p.add_argument("--new-password-env", help="Name of env var holding the new password. "
                   "If omitted, no newPassword is sent (the changer may generate one - test first).")
    p.add_argument("--allow-shared-password", action="store_true",
                   help="Allow the same --new-password-env value on more than one secret")
    p.add_argument("--expire", action="store_true",
                   help="Trigger RPC via POST /secrets/{id}/expire (generated password) "
                        "instead of /change-password")
    p.add_argument("--vault-only", action="store_true",
                   help="Only update the stored value (PUT /secrets/{id}/fields/{slug}); RPC is NOT run and "
                        "the target account is NOT changed. Requires --new-password-env")
    p.add_argument("--field-slug", default="password",
                   help="Field slug to update with --vault-only (default: password)")
    p.add_argument("--comment", help="Comment/reason recorded with the change")
    p.add_argument("--verify", action="store_true",
                   help="After each change, run a heartbeat and wait for lastHeartBeatStatus")
    p.add_argument("--verify-timeout", type=int, default=60, help="Seconds to wait for each verify (default 60)")
    p.add_argument("--delay", type=float, default=1.0, help="Seconds to pause between secrets")
    args = p.parse_args()

    ids = load_ids(args)
    if not ids:
        p.error("Provide --ids and/or --ids-file")
    if args.expire and args.new_password_env:
        p.error("--expire uses a generated password; it cannot be combined with --new-password-env")
    if args.vault_only and args.expire:
        p.error("--vault-only and --expire cannot be combined")
    if args.vault_only and not args.new_password_env:
        p.error("--vault-only requires --new-password-env (the value to store)")

    base_url = os.environ.get("SS_BASE_URL", "").rstrip("/")
    if not base_url:
        print("Missing environment variable: SS_BASE_URL", file=sys.stderr)
        return 2

    if not args.execute:
        print("DRY RUN - no changes will be made. Add --execute to run.")
        for sid in ids:
            if args.vault_only:
                print(f"  would PUT  {base_url}/api/v1/secrets/{sid}/fields/{args.field_slug} (vault only, no RPC)")
            else:
                action = "expire" if args.expire else "change-password"
                print(f"  would POST {base_url}/api/v1/secrets/{sid}/{action}")
        return 0

    missing = [v for v in ("SS_USERNAME", "SS_PASSWORD") if not os.environ.get(v)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    verify_tls = os.environ.get("SS_VERIFY_TLS", "true").lower() != "false"
    if not verify_tls:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("WARNING: TLS verification is disabled (SS_VERIFY_TLS=false).", file=sys.stderr)

    new_password = None
    if args.new_password_env:
        new_password = os.environ.get(args.new_password_env)
        if not new_password:
            print(f"Env var {args.new_password_env} is not set", file=sys.stderr)
            return 2
        if len(ids) > 1 and not args.allow_shared_password:
            print("Refusing to apply the same password to multiple secrets. "
                  "Let the changer generate per-secret passwords, or pass --allow-shared-password.",
                  file=sys.stderr)
            return 2

    ss = SecretServer(base_url, verify_tls)
    try:
        ss.authenticate()
    except (RuntimeError, requests.RequestException) as exc:
        print(exc, file=sys.stderr)
        return 2

    failures, unknown, verify_failed = [], [], []

    for sid in ids:
        try:
            resp = change_password(ss, sid, new_password, args.comment, args.expire,
                                   args.vault_only, args.field_slug)
            if resp.ok:
                print(f"[OK]   secret {sid}: request accepted (HTTP {resp.status_code})")
                if args.verify:
                    status = verify_secret(ss, sid, args.verify_timeout)
                    print(f"       heartbeat status: {status}")
                    if not status.lower().startswith("success"):
                        verify_failed.append(sid)
            else:
                print(f"[FAIL] secret {sid}: HTTP {resp.status_code} {resp.text[:300]}")
                failures.append(sid)
        except (requests.Timeout, requests.ConnectionError) as exc:
            # The server may have received and executed the request.
            print(f"[UNKNOWN] secret {sid}: {type(exc).__name__} - the change may still have run; "
                  "check this secret before retrying")
            unknown.append(sid)
        except (RuntimeError, requests.RequestException) as exc:
            print(f"[FAIL] secret {sid}: {exc}")
            failures.append(sid)
        time.sleep(args.delay)

    ok = len(ids) - len(failures) - len(unknown)
    print(f"\nDone. {ok} accepted, {len(failures)} failed, {len(unknown)} unknown.")
    if failures:
        print("Failed IDs:  ", " ".join(map(str, failures)))
    if unknown:
        print("Unknown IDs (check before retrying):", " ".join(map(str, unknown)))
    if verify_failed:
        print("Heartbeat not successful:", " ".join(map(str, verify_failed)))
    return 1 if (failures or unknown or verify_failed) else 0


if __name__ == "__main__":
    sys.exit(main())
