#!/usr/bin/env bash
set -euo pipefail

: "${LIGHTSAIL_SSH_KEY:?Add the LIGHTSAIL_SSH_KEY repository secret}"
key_file="${1:?Provide the temporary output path}"
if [[ -e "$key_file" || -L "$key_file" ]]; then
  printf 'Refusing to overwrite an existing SSH key file.\n' >&2
  exit 1
fi

umask 077
key_ready=false
trap 'if [[ "$key_ready" != true ]]; then rm -f -- "$key_file"; fi' EXIT

# Raw OpenSSH/PEM keys remain supported. Base64 avoids clipboard line wrapping
# when copying the key from the Lightsail browser terminal into GitHub.
payload="$(printf '%s' "$LIGHTSAIL_SSH_KEY" | tr -d '\r')"
if [[ "$payload" == *'-----BEGIN '*'PRIVATE KEY-----'* ]]; then
  printf '%s\n' "$payload" > "$key_file"
else
  if ! printf '%s' "$payload" | tr -d '[:space:]' | base64 --decode > "$key_file"; then
    printf '::error::LIGHTSAIL_SSH_KEY is not a private key or valid base64. Copy the complete output of base64 -w 0 ~/.ssh/nididhya_github_actions into that GitHub secret.\n' >&2
    exit 1
  fi
  printf '\n' >> "$key_file"
fi

chmod 600 "$key_file"
if ! ssh-keygen -y -P '' -f "$key_file" > /dev/null; then
  printf '::error::LIGHTSAIL_SSH_KEY could not be read as an unencrypted private key. Replace it with the complete base64 output from the validated original key. Do not use the .pub file.\n' >&2
  exit 1
fi

key_ready=true
printf 'SSH private key validated.\n'
