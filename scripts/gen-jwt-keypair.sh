#!/usr/bin/env bash
# Generate an RS256 keypair for the signed wall — to STDOUT only.
#
# The PRIVATE key is held by the identity service (it signs tokens). The PUBLIC
# key is distributed to the gateway and the event-store (they verify tokens).
# This helper PRINTS both to stdout so a human can place them in the secret store
# (Infisical) under the names below. It NEVER writes a key into the repo and the
# repo NEVER commits a key value.
#
# Secret names (see ops/ENV.md):
#   clss.identity.dev.jwt_private_key   <- the PRIVATE key (identity ONLY)
#   clss.gateway.dev.jwt_public_key     <- the PUBLIC key (gateway)   == CLSS_GATEWAY_DEV_JWT_PUBLIC_KEY
#   clss.eventstore.dev.jwt_public_key  <- the PUBLIC key (event-store, same value)
#
# Uses openssl (no project dependency). RS256 == RSA-2048 + SHA-256.
set -euo pipefail

tmp_priv="$(mktemp)"
trap 'rm -f "$tmp_priv"' EXIT

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$tmp_priv" 2>/dev/null

echo "=== PRIVATE KEY (clss.identity.dev.jwt_private_key — identity ONLY, never distribute) ==="
cat "$tmp_priv"
echo
echo "=== PUBLIC KEY (clss.gateway.dev.jwt_public_key / clss.eventstore.dev.jwt_public_key) ==="
openssl pkey -in "$tmp_priv" -pubout
echo
echo "# Place the PRIVATE key in the secret store under clss.identity.dev.jwt_private_key."
echo "# Place the PUBLIC key under clss.gateway.dev.jwt_public_key (== CLSS_GATEWAY_DEV_JWT_PUBLIC_KEY)"
echo "# and clss.eventstore.dev.jwt_public_key. Do NOT commit either value to the repo."
