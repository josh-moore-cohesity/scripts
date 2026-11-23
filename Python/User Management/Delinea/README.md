# Change Delinea Secret Server Passwords Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`delinea_update_password.py` triggers password changes on one or more Delinea Secret Server secrets through the Secret Server REST API. It authenticates with the OAuth2 [token endpoint](https://updates.thycotic.net/secretserver/restapiguide/TokenAuth/) (`/oauth2/token`, password grant) and then calls `POST /api/v1/secrets/{id}/change-password` (or `POST /api/v1/secrets/{id}/expire` with `--expire`), which runs Remote Password Changing (RPC) so the password is changed on the target account as well as in the vault.

The script is a dry run by default. Nothing is changed until you pass `--execute`.

## Requirements

* Python 3.9 or later
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* A Secret Server API user with permission to change the target secrets
* The API user's password, supplied by a hidden prompt, a locally saved (encrypted on Windows) copy, or the `SS_PASSWORD` environment variable. Nothing is hardcoded and no extra modules are needed

## Components

* `delinea_update_password.py` - the main script

## Environment Variables

| Variable | Description |
| --- | --- |
| `SS_BASE_URL` | Required. Base URL, e.g. `https://secretserver.example.com/SecretServer` |
| `SS_USERNAME` | Optional. API user. Prompted for when run interactively if not set |
| `SS_PASSWORD` | Optional. API user's password, for automation. Avoid this where possible; see [Password Handling](#password-handling) |
| `SS_DOMAIN` | Optional. Domain for AD users |
| `SS_OTP` | Optional. One-time code if the API user requires 2FA (sent as the `OTP` header) |
| `SS_VERIFY_TLS` | Optional. Set to `false` to skip TLS verification (not recommended) |

## Password Handling

The API user's password never has to be placed in an environment variable or on the command line. The script looks for it in this order:

1. The `SS_PASSWORD` environment variable (for automation).
2. A password saved in `~/.delinea_secretserver/credentials.json`, keyed by server and user.
3. A hidden prompt (interactive only). After the first successful login the typed password is saved for next time, unless you pass `--no-save-password`.

Save the password once, ahead of time (hidden prompt, nothing is echoed or logged):

```
python delinea_update_password.py --store-password
```

Remove it again:

```
python delinea_update_password.py --clear-password
```

How the saved password is protected:

* **Windows:** encrypted with DPAPI (built in to Windows, called through `ctypes`). Only the same Windows user on the same machine can decrypt it, so a copied file is of no use elsewhere.
* **Other operating systems:** only base64-encoded in an owner-only file. That is obfuscation, not encryption (the same level as `pyhesity.py`); prefer `SS_PASSWORD` fed from a secret store there. The script prints which method it used each time it saves.

If a saved password is rejected, the script says so; re-enter it with `--store-password`.

## Operating Modes

### Dry Run (default)

Show which calls would be made, without authenticating or changing anything:

```
python delinea_update_password.py --ids 101 102 103
```

### Generated Password

Let each secret's password changer generate the new password:

```
python delinea_update_password.py --ids 101 102 --execute
```

Trigger RPC with a generated password through the expire endpoint instead:

```
python delinea_update_password.py --ids 101 102 --execute --expire
```

### Specific Password

Use a specific new password, read from an environment variable:

```
python delinea_update_password.py --ids 101 --execute --new-password-env NEW_SECRET_PW
```

### Vault Only (no RPC)

Store a known password in the secret without running Remote Password Changing. The target account is **not** changed, so use this only when the password was already changed elsewhere and the vault needs to catch up:

```
python delinea_update_password.py --ids 101 --execute --vault-only --new-password-env NEW_SECRET_PW
```

Update a different field (default is `password`) and confirm the vaulted value works with a heartbeat:

```
python delinea_update_password.py --ids 101 --execute --vault-only --field-slug password --new-password-env NEW_SECRET_PW --verify
```

### IDs From a File, With Audit Comment and Verification

Read secret IDs from a file (one per line, `#` comments allowed), record a comment, then heartbeat each secret and wait for the result:

```
python delinea_update_password.py --ids-file ids.txt --execute --comment "CHG0012345 rotation" --verify
```

## Parameters

### Credentials

| Flag | Description |
| --- | --- |
| `--store-password` | Optional. Prompt (hidden) for the API user's password, save it locally, then exit |
| `--clear-password` | Optional. Remove the saved password for this server/user, then exit |
| `--no-save-password` | Optional. Do not save a password that was typed at the prompt |

### Selecting Secrets

| Flag | Description |
| --- | --- |
| `--ids` | One or more secret IDs (at least one of `--ids` or `--ids-file` is required) |
| `--ids-file` | File with one secret ID per line; `#` comments (including inline) are allowed |

### Change Options

| Flag | Description |
| --- | --- |
| `--execute` | Optional. Actually change passwords (default is dry run) |
| `--new-password-env` | Optional. Name of an environment variable holding the new password. If omitted, no `newPassword` is sent |
| `--allow-shared-password` | Optional. Permit the same `--new-password-env` value on more than one secret (refused by default) |
| `--expire` | Optional. Use `POST /secrets/{id}/expire` (generated password). Cannot be combined with `--new-password-env` |
| `--vault-only` | Optional. Only update the stored value with `PUT /secrets/{id}/fields/{slug}`; RPC is not run and the target is not changed. Requires `--new-password-env`; cannot be combined with `--expire` |
| `--field-slug` | Optional. Field to update with `--vault-only` (default `password`) |
| `--comment` | Optional. Comment/reason recorded with the change |
| `--delay` | Optional. Seconds to pause between secrets (default 1.0) |

### Verification

| Flag | Description |
| --- | --- |
| `--verify` | Optional. After each change, run a heartbeat and poll `lastHeartBeatStatus` until it settles |
| `--verify-timeout` | Optional. Seconds to wait for each verification (default 60) |

## Behavior

* **Re-authentication:** Secret Server tokens expire (about 20 minutes by default). On a 401 the script re-authenticates once and retries. It also backs off and retries on 429, 502, 503 and 504.
* **Accepted is not completed:** a successful HTTP response only means the request was accepted. RPC can run asynchronously, so use `--verify` to confirm the result.
* **Timeouts are reported as UNKNOWN:** if a request times out or the connection drops, the change may still have run. The script lists these secrets separately; check them before re-running to avoid a second change or an account lockout.
* **Exit code:** non-zero if any secret failed, is unknown, or did not report a successful heartbeat.

## Notes

* The saved-password file is per user and per server. Keep `SS_BASE_URL` and `SS_DOMAIN` consistent between `--store-password` and later runs, or the script will not find the saved password and will prompt again.
* Confirm the endpoint schemas against your instance's Swagger page (`<SS_BASE_URL>/swagger`); parameters can differ between Secret Server versions.
* The script sends `autoCheckout`, `autoCheckIn` and `autoComment` query parameters to `/change-password`. It has not been confirmed that this endpoint honours them, so secrets that require check-out or a comment may fail. Test with one low-risk secret first.
* `--vault-only` sends `{"value": "<password>"}` to `PUT /api/v1/secrets/{id}/fields/{slug}`; this body shape has not been confirmed on every version, so check Swagger first. Unlike the whole-object `PUT /secrets/{id}` shown in Delinea's [Python 3 REST example](https://docs.delinea.com/online-help/secret-server/api-scripting/rest-api/rest-api-python3-scripts/index.htm), it touches only the one field. Either way the vault is updated and the target account is not, so combine it with `--verify` to confirm the vaulted password actually works.
* Omitting `newPassword` may not cause the changer to generate a password on every version; use `--expire` if it does not.
* Applying one password to many secrets is discouraged. Prefer generated per-secret passwords.
* If a specific new password is supplied and the remote change fails, the vault and the target account can be out of sync.
* A stale `lastHeartBeatStatus` from an earlier heartbeat can be read before the new heartbeat starts when using `--verify`.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Delinea/delinea_update_password.py
```
