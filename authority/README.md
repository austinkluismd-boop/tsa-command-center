# Atlas Authority Command Center

`authority/index.html` is the estate's tenant console: a tabbed view of the
full corpus per tenant (**Composite · TSA · OSA · Bella Roma · TSA
Wellness**), Site Studio (edit requests + data patches), Media Library,
Socials & OAuth, and the Atlas Assistant (Claude on Amazon Bedrock).

It obeys the three estate laws (see the repo's `CLAUDE.md`):

- **Provenance** — every chip is derived at render time from `CC_DATA`
  provenance fields (`PROV_CLASS`); the file contains no hardcoded MEASURED
  chip and the `console-verify` battery proves it on every push.
- **Zero network** — fonts embedded, no CDN, no remote images. The page
  loads with **zero requests**; only explicit sign-in / workspace actions
  ever touch the network.
- **One pathway** — the console carries the same `window.CC_DATA` line as
  the flagship, byte-for-byte, and `tools/ccdata.py patch` rewrites desktop,
  mobile **and** this console in one operation. Every edit surface in the
  console (chat proposals, Studio drafts, media swaps) terminates in that
  pathway or in the change-request queue — never in a hand edit.

The console has two halves:

| Half | Where | Contains |
|---|---|---|
| Public shell | this repo → GitHub Pages | UI + embedded CC_DATA snapshot. No secrets, no hostnames beyond the estate's public domains. |
| Private workspace | `authority/backend/` deployed to the operator's AWS account | Cognito login, Claude on Bedrock, change-request queue, S3 media vault, Secrets Manager OAuth vault, GitHub PR hand-off. |

Offline (no workspace connected) the console is a read-only demo of the
embedded snapshot and says so; it never fakes a queue, a vault, or an AI.

---

## Deploying the workspace (one-time, ~15 minutes)

Prereqs: an AWS account + credentials, [AWS SAM CLI], Python 3.12.

### 1. Enable Claude on Bedrock

In the AWS console → **Amazon Bedrock → Model access** (in the region you
will pass as `BedrockRegion`), request/enable access to Anthropic Claude
models. The stack defaults to the current Opus-tier model id; override
`BedrockModelId` at deploy time if your region exposes it under an
inference-profile id (e.g. a `us.anthropic.…` profile) — the IAM policy in
the template already covers both forms.

### 2. Deploy

```bash
cd authority/backend
sam build
sam deploy --guided        # pick a stack name like atlas-authority
```

Guided prompts to answer:

- `AllowedOrigin` — where the console is served, default
  `https://austinkluismd-boop.github.io` (CORS is locked to it).
- `BedrockRegion` / `BedrockModelId` — from step 1.
- `GitHubRepo` — default `austinkluismd-boop/tsa-command-center`.

The deploy prints **`WorkspaceConfig`** — a one-line JSON blob. That blob is
the console's connection setting (IDs only, no secrets).

### 3. Connect the console

Open the console → **Demo access** → **Access & Workspace** → paste the
`WorkspaceConfig` JSON → **Save connection** → **Test**.

### 4. Create the logins (Dr. Cuzalina, Samantha)

Accounts are invitations — no self-signup, no shared passwords. Cognito
emails a temporary password; first sign-in forces a new one.

```bash
POOL=<UserPoolId from the deploy outputs>

# Dr. Cuzalina — owner (reviews & approves, full configuration)
aws cognito-idp admin-create-user --user-pool-id $POOL \
  --username drcuzalina@example.com \
  --user-attributes Name=email,Value=drcuzalina@example.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL \
  --username drcuzalina@example.com --group-name owners

# Samantha — editor (drafts edits, uploads media, configures socials/OAuth)
aws cognito-idp admin-create-user --user-pool-id $POOL \
  --username samantha@example.com \
  --user-attributes Name=email,Value=samantha@example.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL \
  --username samantha@example.com --group-name editors
```

(Substitute their real addresses. Add yourself to `owners` the same way.
To let Sam approve as well, put her in `owners` instead.)

What to send each of them: the console URL, the `WorkspaceConfig` blob
(or connect it for them once — it persists in the browser), and "check
your email for the temporary password". Sign-in lives behind the
**Workspace sign-in** button on the gate.

Roles: **owners** approve change requests and can delete credentials;
**editors** draft edits, upload media, and save OAuth credentials; anyone
signed in can chat with the Atlas Assistant and read the queue.

### 5. GitHub hand-off (data patches → PRs)

Create a **fine-grained GitHub token** scoped to this repo only, with
*Contents: Read and write* and *Pull requests: Read and write*, then store
it in Secrets Manager under the name the stack expects:

```bash
aws secretsmanager create-secret \
  --name atlas/authority/github-token \
  --secret-string '{"token":"github_pat_..."}'
```

From then on, approving a `data_patch` change request commits the patch
file to a fresh `authority/patch/<date>-<id>` branch and opens a **draft
PR**. The repo's `apply-authority-patch` workflow applies it via
`tools/ccdata.py` (desktop + mobile + authority in one operation) and
`console-verify` gates the merge — the token never needs, and should never
have, permission to push to `main`.

### 6. What the Atlas Assistant can and cannot do

Connected chat goes to `POST /chat` → Claude on Bedrock with two tools:
`propose_site_edit` and `propose_data_patch`. Both create **pending**
change requests; nothing executes until an owner approves in Site Studio.
The chat function has no write access to any console file — the
one-pathway law is enforced by IAM, not by prompting.

### 7. Socials & OAuth (Sam's panel)

Handles/links shown in the console come from the `CC_DATA` social ledger
(changing one is a data patch, so every console updates at once). App
credentials for publishing (Meta, Google Business, TikTok, YouTube, X) are
saved from the Socials & OAuth view straight into Secrets Manager
(`atlas/authority/social/<platform>`); the API only ever reports
*configured / not configured* and never echoes a secret. Deleting schedules
a 7-day recovery window.

---

## Security posture (read before sharing the URL)

- This repo is **public**. The console page contains no secrets and no
  private hostnames; the workspace config is IDs only. Keep it that way.
- The gate on the public page is a door, not a lock: real authorization
  happens server-side (Cognito JWT on every API route). Anyone can view
  the demo snapshot — that is by design; it is the same data the flagship
  demo already publishes.
- Cognito is invitation-only with enforced password rotation on first
  sign-in and advanced security mode ENFORCED.
- CORS is pinned to the Pages origin; media uploads are presigned,
  image-typed, and size-capped; the vault bucket is private + versioned.
- Every privileged action (chat, create/approve/reject, upload, credential
  write) lands in the audit log with the acting identity.

[AWS SAM CLI]: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
