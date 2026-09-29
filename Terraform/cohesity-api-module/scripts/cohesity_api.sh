#!/usr/bin/env bash
#
# Reads a JSON object from stdin (Terraform's `external` data source
# contract), authenticates to a Cohesity cluster or to Helios, performs one
# GET call against the public v1 API, and prints a flat JSON object back to
# stdout.
#
# Requires: bash, curl, jq

set -euo pipefail

# --- 1. Read Terraform's query object from stdin -----------------------
INPUT_JSON="$(cat)"

AUTH_METHOD=$(echo "$INPUT_JSON"       | jq -r '.auth_method')
CLUSTER_VIP=$(echo "$INPUT_JSON"       | jq -r '.cluster_vip')
USERNAME=$(echo "$INPUT_JSON"          | jq -r '.username')
PASSWORD=$(echo "$INPUT_JSON"          | jq -r '.password')
DOMAIN=$(echo "$INPUT_JSON"            | jq -r '.domain')
API_KEY=$(echo "$INPUT_JSON"           | jq -r '.api_key')
KEY_VAULT_NAME=$(echo "$INPUT_JSON"    | jq -r '.key_vault_name')
KEY_VAULT_SECRET_NAME=$(echo "$INPUT_JSON" | jq -r '.key_vault_secret_name')
HELIOS_URL=$(echo "$INPUT_JSON"        | jq -r '.helios_url')
ACCESS_CLUSTER_ID=$(echo "$INPUT_JSON" | jq -r '.access_cluster_id')
ENDPOINT=$(echo "$INPUT_JSON"          | jq -r '.endpoint')
INSECURE=$(echo "$INPUT_JSON"          | jq -r '.insecure')

fail() {
  # external data source expects errors on stderr + non-zero exit
  echo "$1" >&2
  exit 1
}

CURL_OPTS=(-s -S)
if [[ "$INSECURE" == "true" ]]; then
  CURL_OPTS+=(-k)
fi

BASE_URL=""
AUTH_HEADERS=()

# If no api_key was passed in directly, but a Key Vault reference was given,
# fetch it here at run time. This keeps the secret out of Terraform's
# variable graph and state entirely -- only this script ever sees the raw
# value, and only in memory for the life of this process.
if [[ -z "$API_KEY" && -n "$KEY_VAULT_NAME" && -n "$KEY_VAULT_SECRET_NAME" ]]; then
  command -v az >/dev/null 2>&1 || fail "az CLI not found; required to fetch api_key from Key Vault"
  API_KEY=$(az keyvault secret show \
    --vault-name "$KEY_VAULT_NAME" \
    --name "$KEY_VAULT_SECRET_NAME" \
    --query value -o tsv 2>/dev/null) \
    || fail "Failed to fetch secret '${KEY_VAULT_SECRET_NAME}' from Key Vault '${KEY_VAULT_NAME}' -- is 'az login' done and does the identity have Key Vault Secrets User access?"
fi

# --- 2. Build the base URL + auth header(s) for the chosen method ------
case "$AUTH_METHOD" in

  password)
    [[ -n "$CLUSTER_VIP" ]] || fail "cluster_vip is required for auth_method=password"
    BASE_URL="https://${CLUSTER_VIP}"

    AUTH_BODY=$(jq -n --arg u "$USERNAME" --arg p "$PASSWORD" --arg d "$DOMAIN" \
      '{username: $u, password: $p, domain: $d}')

    TOKEN_RESPONSE=$(curl "${CURL_OPTS[@]}" -X POST \
      "${BASE_URL}/irisservices/api/v1/public/accessTokens" \
      -H "Content-Type: application/json" \
      -d "$AUTH_BODY") || fail "Failed to reach ${CLUSTER_VIP} for authentication"

    ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.accessToken // empty')
    TOKEN_TYPE=$(echo "$TOKEN_RESPONSE"   | jq -r '.tokenType // "Bearer"')
    [[ -n "$ACCESS_TOKEN" ]] || fail "Authentication failed. Cluster response: ${TOKEN_RESPONSE}"

    AUTH_HEADERS=(-H "Authorization: ${TOKEN_TYPE} ${ACCESS_TOKEN}")
    ;;

  cluster_api_key)
    [[ -n "$CLUSTER_VIP" ]] || fail "cluster_vip is required for auth_method=cluster_api_key"
    [[ -n "$API_KEY" ]]     || fail "api_key is required for auth_method=cluster_api_key"
    BASE_URL="https://${CLUSTER_VIP}"
    AUTH_HEADERS=(-H "apiKey: ${API_KEY}")
    ;;

  helios_api_key)
    [[ -n "$API_KEY" ]]           || fail "api_key is required for auth_method=helios_api_key"
    [[ -n "$ACCESS_CLUSTER_ID" ]] || fail "access_cluster_id is required for auth_method=helios_api_key"
    BASE_URL="${HELIOS_URL}"
    # accessClusterId tells Helios which registered cluster to proxy this call to.
    # No session/token exchange step -- the apiKey header is enough on every call.
    AUTH_HEADERS=(-H "apiKey: ${API_KEY}" -H "accessClusterId: ${ACCESS_CLUSTER_ID}")
    ;;

  *)
    fail "Unknown auth_method: ${AUTH_METHOD}"
    ;;
esac

# --- 3. Call the requested endpoint: GET /public/<endpoint> ------------
API_RESPONSE=$(curl "${CURL_OPTS[@]}" -X GET \
  "${BASE_URL}/irisservices/api/v1/public/${ENDPOINT}" \
  "${AUTH_HEADERS[@]}") \
  || fail "API call to ${ENDPOINT} failed"

# --- 4. Hand the result back to Terraform -------------------------------
# external data source requires a flat map of string -> string, so we pass
# the API response through as a JSON-encoded string; the module's outputs.tf
# decodes it back into a real object with jsondecode().
jq -n --arg result "$API_RESPONSE" '{"result": $result}'
