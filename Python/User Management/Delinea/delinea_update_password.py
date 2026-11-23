#!/usr/bin/env python3
"""
Change passwords on Delinea Secret Server secrets via the REST API
(POST /api/v1/secrets/{id}/change-password), which runs Remote Password
Changing (RPC) so the password is changed on the target account too.

Usage examples:
    # One-time: prompt (hidden) for the API user's password and save it encrypted locally
    python delinea_update_password.py --store-password

    # Remove the saved password
    python delinea_update_password.py --clear-password

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
    SS_USERNAME   (optional) API user; prompted for when run interactively if not set
    SS_PASSWORD   (optional) API user's password. Avoid keeping this in clear text - see below
    SS_DOMAIN     (optional) domain for AD users
    SS_OTP        (optional) one-time code if the API user requires 2FA (sent as the OTP header)
    SS_VERIFY_TLS (optional) set to "false" to skip TLS verification (not recommended)

Password lookup order (the password is never printed or logged):
    1. SS_PASSWORD environment variable (for automation)
    2. Password saved by --store-password (or by an earlier prompt) in
       ~/.delinea_secretserver/credentials.json. No extra modules are needed.
    3. Hidden prompt (interactive only). After a successful login it is saved for
       next time, unless --no-save-password is given.
    How the saved password is protected:
      * Windows: encrypted with DPAPI (built in to Windows, called through ctypes).
        Only the same Windows user on the same machine can decrypt it, so copying the
        file elsewhere is useless.
      * Other OSes: only base64-encoded (obfuscation, like pyhesity) in a file with
        owner-only permissions. Treat that as "not readable by casual glance", not as
        encryption; prefer SS_PASSWORD from a secret store there.

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
import base64
import ctypes
import getpass
import json
import os
import sys
import time

import requests
import urllib3


CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".delinea_secretserver")
STORE_FILE = os.path.join(CONFIG_DIR, "credentials.json")


# --- Windows DPAPI via ctypes (standard library only) -------------------------------

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.c_void_p)]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_DataBlob)]
    fn.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _DataBlob(len(data), ctypes.cast(buf, ctypes.c_void_p))
    blob_out = _DataBlob()
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _encode(password: str):
    """Returns (method, base64 text) for storing."""
    raw = password.encode("utf-8")
    if os.name == "nt":
        return "dpapi", base64.b64encode(_dpapi(raw, True)).decode("ascii")
    return "b64", base64.b64encode(raw).decode("ascii")


def _decode(method: str, text: str) -> str:
    raw = base64.b64decode(text.encode("ascii"))
    if method == "dpapi":
        if os.name != "nt":
            raise RuntimeError("DPAPI-protected password cannot be read on this OS")
        raw = _dpapi(raw, False)
    elif method != "b64":
        raise RuntimeError(f"unknown storage method {method!r}")
    return raw.decode("utf-8")


def _load_store() -> dict:
    try:
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_store(data: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)  # effective on POSIX; harmless on Windows
    except OSError:
        pass
    tmp = STORE_FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, STORE_FILE)


def credential_key(base_url: str, domain, username: str) -> str:
    """Identifies one stored credential (server + account)."""
    account = f"{domain}\\{username}" if domain else username
    return f"{base_url.lower()}|{account.lower()}"


def get_username():
    """SS_USERNAME, or a prompt when run interactively."""
    user = os.environ.get("SS_USERNAME")
    if user:
        return user
    if sys.stdin.isatty():
        try:
            return input("Secret Server username: ").strip() or None
        except (EOFError, KeyboardInterrupt):
            return None
    return None


def save_password(key: str, password: str) -> bool:
    try:
        method, text = _encode(password)
        store = _load_store()
        store[key] = {"method": method, "data": text}
        _write_store(store)
    except Exception as exc:
        print(f"Could not save the password: {exc}", file=sys.stderr)
        return False
    note = "encrypted with Windows DPAPI" if method == "dpapi" else "base64-encoded only (not encrypted)"
    print(f"Password saved to {STORE_FILE} ({note}).")
    return True


def get_stored_password(key: str):
    entry = _load_store().get(key)
    if not isinstance(entry, dict):
        return None
    try:
        return _decode(entry.get("method", ""), entry.get("data", "")) or None
    except Exception:
        return None  # e.g. file copied from another user/machine; fall through to prompt


def clear_password(key: str) -> bool:
    store = _load_store()
    if key not in store:
        print("No saved password found for this server/user.", file=sys.stderr)
        return False
    del store[key]
    try:
        _write_store(store)
    except Exception as exc:
        print(f"Could not update {STORE_FILE}: {exc}", file=sys.stderr)
        return False
    print("Saved password removed.")
    return True


def resolve_password(key: str, label: str, force_prompt: bool = False):
    """Find the password. Returns (password, source) where source is
    'environment', 'stored', 'prompt' or 'none'. Nothing is saved here."""
    if not force_prompt:
        env_pw = os.environ.get("SS_PASSWORD")
        if env_pw:
            return env_pw, "environment"
        stored = get_stored_password(key)
        if stored:
            return stored, "stored"
    if sys.stdin.isatty():
        try:
            entered = getpass.getpass(f"Secret Server password for {label}: ")
        except (EOFError, KeyboardInterrupt):
            entered = None
        if entered:
            return entered, "prompt"
    return None, "none"


class SecretServer:
    """Thin client: one Session, bearer token, automatic re-auth on 401."""

    def __init__(self, base_url: str, verify: bool, username: str, password: str, domain=None):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = verify
        self.username = username
        self._password = password
        self.domain = domain
        self.token = None

    def authenticate(self) -> None:
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self._password,
        }
        if self.domain:
            data["domain"] = self.domain
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
    p.add_argument("--store-password", action="store_true",
                   help="Prompt for the API user's password and save it locally "
                        "(Windows DPAPI-encrypted), then exit")
    p.add_argument("--clear-password", action="store_true",
                   help="Remove the saved password for this server/user, then exit")
    p.add_argument("--no-save-password", action="store_true",
                   help="Do not save a password that was typed at the prompt")
    args = p.parse_args()

    ids = load_ids(args)
    manage_creds = args.store_password or args.clear_password
    if args.store_password and args.clear_password:
        p.error("--store-password and --clear-password cannot be combined")
    if not ids and not manage_creds:
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

    domain = os.environ.get("SS_DOMAIN") or None

    if manage_creds:
        username = get_username()
        if not username:
            print("Set SS_USERNAME (or run interactively) so the credential can be identified.", file=sys.stderr)
            return 2
        key = credential_key(base_url, domain, username)
        label = f"{domain}\\{username}" if domain else username
        if args.clear_password:
            return 0 if clear_password(key) else 1
        pw, _ = resolve_password(key, f"{label} at {base_url}", force_prompt=True)
        if not pw:
            print("No password entered (this needs an interactive terminal).", file=sys.stderr)
            return 2
        return 0 if save_password(key, pw) else 1

    if not args.execute:
        print("DRY RUN - no changes will be made. Add --execute to run.")
        for sid in ids:
            if args.vault_only:
                print(f"  would PUT  {base_url}/api/v1/secrets/{sid}/fields/{args.field_slug} (vault only, no RPC)")
            else:
                action = "expire" if args.expire else "change-password"
                print(f"  would POST {base_url}/api/v1/secrets/{sid}/{action}")
        return 0

    username = get_username()
    if not username:
        print("Missing username: set SS_USERNAME or run interactively.", file=sys.stderr)
        return 2
    key = credential_key(base_url, domain, username)
    label = f"{domain}\\{username}" if domain else username
    password, pw_source = resolve_password(key, f"{label} at {base_url}")
    if not password:
        print("No password available. Run with --store-password first, set SS_PASSWORD, "
              "or run in an interactive terminal to be prompted.", file=sys.stderr)
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

    ss = SecretServer(base_url, verify_tls, username, password, domain)
    try:
        ss.authenticate()
    except (RuntimeError, requests.RequestException) as exc:
        print(exc, file=sys.stderr)
        if pw_source == "stored":
            print("If the password has changed, update the saved one with --store-password.", file=sys.stderr)
        return 2
    # Save a typed password only after it has been proven to work.
    if pw_source == "prompt" and not args.no_save_password:
        save_password(key, password)

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
