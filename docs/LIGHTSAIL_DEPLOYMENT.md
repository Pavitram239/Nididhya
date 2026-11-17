# Automatic deployment to Lightsail

This setup updates the existing Docker Compose app as `ubuntu` in `/home/ubuntu/vachanamrut_app`. GitHub runs the topic-link tests and frontend build, then deploys the tested commit over SSH.

## 1. Check the server

Open your instance's **Connect using SSH** console and run:

```bash
cd /home/ubuntu/vachanamrut_app
git branch --show-current
docker compose version
docker compose ps
GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -o BatchMode=yes' git ls-remote origin refs/heads/master
```

The branch should be `master`. Docker Compose and Git access must work as `ubuntu` without a password or interactive login. Keep the app's existing `.env` on the server.

The confirmed public IPv4 address is **13.234.251.117**. Keep it attached as a static IP in Lightsail so deployment settings remain valid after instance stops/starts.

## 2. Create a dedicated deployment key

Run this once in the trusted Lightsail SSH console. If this key already exists, skip this section and reuse it; do not regenerate it to update a GitHub secret. The command refuses to overwrite an existing key:

```bash
(
  set -eu
  deploy_key="$HOME/.ssh/nididhya_github_actions"
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  if [ -e "$deploy_key" ] || [ -e "$deploy_key.pub" ]; then
    echo 'Deployment key already exists. Stop here and reuse it only if it is the intended key.'
    exit 1
  fi
  ssh-keygen -t ed25519 -C 'github-actions-nididhya' -f "$deploy_key" -N ''
  printf '\nrestrict %s\n' "$(cat "$deploy_key.pub")" >> "$HOME/.ssh/authorized_keys"
  chmod 600 "$HOME/.ssh/authorized_keys"
)
```

The public key is now authorized for this account, with forwarding and terminal allocation restricted. The workflow uses command execution over SSH. [OpenSSH key options](https://man.openbsd.org/sshd.8#AUTHORIZED_KEYS_FILE_FORMAT)

## 3. Add three GitHub secrets

Open [the repository's Actions secrets](https://github.com/Pavitram239/Nididhya/settings/secrets/actions), then choose **New repository secret** for each row. This is **Settings → Secrets and variables → Actions → Secrets**. [GitHub instructions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)

| Name | Value |
| --- | --- |
| `LIGHTSAIL_HOST` | `13.234.251.117` |
| `LIGHTSAIL_SSH_KEY` | The one-line base64 encoding of the existing private key from the command below |
| `LIGHTSAIL_KNOWN_HOSTS` | The trusted host-key line from the following command |

To copy the existing private key as one line in the Lightsail console:

```bash
base64 -w 0 ~/.ssh/nididhya_github_actions
printf '\n'
```

Copy the whole encoded line **directly into the existing `LIGHTSAIL_SSH_KEY` secret on GitHub**. It may wrap visually in the console; copy all of it. Encoding does not make the private key public or safe to share: do not paste it into chat, commit it, or share it elsewhere. The workflow's key-preparation helper accepts either this one-line base64 value or the original complete multiline private key, but base64 avoids line-break damage while copying. Keep the same secret name; the other two secrets do not change.

For `LIGHTSAIL_KNOWN_HOSTS`, run this in that same trusted console:

```bash
LIGHTSAIL_IP='13.234.251.117'
printf '%s %s\n' "$LIGHTSAIL_IP" "$(cut -d ' ' -f 1,2 /etc/ssh/ssh_host_ed25519_key.pub)"
```

Copy its single output line into the secret. This pins the actual server key; the workflow does not trust a fresh network scan or disable host verification. [OpenSSH host-key format](https://man.openbsd.org/sshd.8#SSH_KNOWN_HOSTS_FILE_FORMAT)

## 4. Run the first deployment manually

Once `.github/workflows/deploy-lightsail.yml` and `scripts/deploy-lightsail.sh` are on `master`:

1. Open **Actions → Deploy to Lightsail → Run workflow**.
2. Select `master`, then **Run workflow**.
3. Wait for both validation and deployment to pass.
4. Open the app and verify that the topic entry for master ID 539 opens chapter 3, vat 4.

Automatic deployment is initially disabled. Pushes still run validation, but deployment is skipped until the next step. A manual run on `master` can deploy without the variable.

### If SSH reports `error in libcrypto`

In the trusted Lightsail SSH console, validate the existing original key without printing its contents:

```bash
ssh-keygen -y -P '' -f ~/.ssh/nididhya_github_actions >/dev/null
```

Successful validation prints nothing. If that command succeeds, copy the key again using the base64 command in step 3 and update only the existing `LIGHTSAIL_SSH_KEY` secret. Do not create a new key or another secret name. If validation fails, stop and report the error text without sharing the key.

After a workflow or helper change has been pushed, start a **new** run through **Actions → Deploy to Lightsail → Run workflow → master**. Do not select **Re-run jobs** on an older failure: a rerun uses that run's original commit and ref, so it does not pick up a newly pushed fix. [GitHub rerun behavior](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)

## 5. Enable deployment after each push

On **Settings → Secrets and variables → Actions → Variables**, add:

| Name | Value |
| --- | --- |
| `LIGHTSAIL_DEPLOY_ENABLED` | `true` |

Future pushes to `master` now validate and deploy automatically. Set this variable to `false` to pause automatic deployment; manual runs remain available.

## What deployment changes

The script fast-forwards to the tested commit, builds the images, starts and checks the backend, then recreates and checks the frontend. It refreshes the frontend's anonymous `node_modules` volume so dependency updates take effect. The server's `.env` and bind-mounted scripture/database files are retained; there is no automatic Git reset, clean, database reindex, or volume purge.

The running database is tracked in this repository and can have local changes. If an update conflicts with server files, deployment stops for review instead of discarding them. Container recreation can briefly interrupt requests; a failed deployment is reported and does not promise automatic rollback.

If SSH times out, check that the existing Lightsail network policy permits the runner's connection. Do not broaden the firewall or bypass host verification just to silence a connection failure. If Git or Docker asks for a password, finish that server prerequisite before enabling automatic deployment.
