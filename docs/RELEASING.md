# Releasing neutrino-database (and verifying what prod runs)

`neutrino_database` is not on PyPI. Every Python service installs it from git at
image build time, so **which ref a service was built against is part of the
service's supply chain** (security gap G-28), and the service images themselves
must be provable (G-27). This page is the process for both.

## 1. Which ref each environment installs

| Where | Ref | Set by |
|---|---|---|
| Local dev / tests | `requirements.txt` line: `neutrino_database @ git+https://github.com/Neutrino-Engine/neutrino-database.git@uat` | the line itself; `make install-db-remote NEUTRINO_DB_REF=<ref>` overrides |
| Dockerfile default | `ARG NEUTRINO_DB_REF=release-cmd` | a build that passes nothing gets promoted code, never `dev` |
| Jenkins (dev, UAT) | `--build-arg NEUTRINO_DB_REF=${ENVIRONMENT.toLowerCase()}` → `dev` / `uat` | the `NeutrinoDeployment` job (inline pipeline on the Jenkins controller) |
| Prod (`deploy-prod.yml`) | release-train dispatch → `workflow_dispatch` input `neutrino_db_ref` → `release-cmd` | the service workflow's `NEUTRINO_DB_REF` env |

Every Dockerfile filters the `neutrino[_-]database` line out of `requirements.txt`
and installs `NEUTRINO_DB_REF` first, so the requirements line can never override
the build arg. (`neutrino-workflow-service/Dockerfile.worker` did not filter before
T9; it does now.)

The org is `Neutrino-Engine`. `8bitai/...` URLs still resolve through GitHub's
rename redirect, but a redirect is a supply-chain hop we do not want: if the old
org name were ever re-registered, every build would install from it.

## 2. Tag releases (semver on `release-cmd`)

Branch flow is unchanged: feature → `uat` → `release-cmd`. A **tag names the exact
`release-cmd` commit a prod release was built from**, so a service build can be
pinned to it and a human can read it.

1. Merge the `uat → release-cmd` PR. The push triggers `deploy-prod.yml` here: it
   builds the migration image from `release-cmd` HEAD, runs `make migrate` in prod,
   then dispatches every dependent service to rebuild with
   `neutrino_db_ref=<12-char commit sha>`. That sha is immutable; the tag is the
   label for it.
2. Tag that commit. Bump by semver meaning of the schema change:
   - **major** — a migration drops or renames a column/table, or changes a model
     in a way that breaks a service that has not been updated;
   - **minor** — additive migrations, new models, new FGA relations;
   - **patch** — no migration (docs, helpers, model metadata).
   ```sh
   git fetch origin release-cmd
   git tag -a v1.3.0 -m "NC-xxxx: <one line>" origin/release-cmd
   git push origin v1.3.0
   ```
   The `jira` ruleset blocks new *branches*, not tags.
3. Record the tag in the release PR description of each service that was rebuilt.
   Prod builds of services are reproducible from `workflow_dispatch` with
   `neutrino_db_ref: v1.3.0` (the input accepts a tag or a commit).

Rules:
- Tags are immutable. A bad release gets a new tag, never a moved one.
- `setup.py` `version` stays `0.1.0` until the package is published somewhere that
  reads it; the git tag is the version.
- A service must never ship to prod against `dev` or `uat`. `deploy-prod.yml`'s
  default is `release-cmd`; passing `dev` there is a review failure.

## 3. What `deploy-prod.yml` now proves (G-27)

Each service's `deploy-prod.yml` (and this repo's migration image) does, after
`docker buildx build --push`:

1. reads the pushed digest from `--metadata-file`;
2. `actions/attest-build-provenance` — SLSA build provenance, stored by GitHub and
   pushed to ACR as an OCI referrer of the digest (`continue-on-error` until a prod
   run shows it works on this plan — artifact attestations on private repos need
   GitHub Enterprise Cloud);
3. `syft` — SPDX SBOM of the image;
4. `cosign sign` — keyless (Sigstore / Fulcio) signature of the digest, identity =
   this workflow file at this ref, issued against the GitHub Actions OIDC token;
5. `cosign attest --type spdxjson` — the SBOM attached as a signed attestation;
6. `cosign verify` + `cosign verify-attestation` against the expected identity —
   **the deploy step does not run unless verification passes**;
7. `helm upgrade --set image.tag=<sha>@<digest>` — the pod spec names the digest,
   so what was signed is what runs, even if the tag is later overwritten.

`syft` and `cosign` are downloaded as release binaries with a pinned version and a
sha256 check (same pattern as trivy in `pr.yml`); no third-party actions. The job
carries `id-token: write` only for that one job (Azure login + Sigstore need it),
`attestations: write` for the provenance step, and `contents: read` otherwise.

### Why cosign keyless, not Notation + Azure Key Vault

Both work with ACR and Ratify. Keyless wins here because:

- **no key to manage** — Notation needs a Key Vault signing key, a cert chain, a
  rotation plan and RBAC for the pipeline; keyless binds the signature to the
  workflow's OIDC identity and a short-lived cert in Rekor;
- **one verifier chain** — `attest-build-provenance` is Sigstore too, so provenance
  and signature verify with the same tooling and the same identity;
- **nothing to steal** — the Key Vault key in the Notation model is a long-lived
  secret the pipeline must be able to use; a stolen one signs anything.

Notation is the right choice only if a policy forbids external transparency logs
(Rekor is public; the image name and digest, not the contents, are logged).

### Verify an image by hand

```sh
IMG=crneutrinoprodcin001.azurecr.io/agent-platform@sha256:<digest>
ID='https://github.com/Neutrino-Engine/agent-platform/.github/workflows/deploy-prod.yml@refs/heads/release-cmd'
ISS=https://token.actions.githubusercontent.com

az acr login --name crneutrinoprodcin001
cosign verify "$IMG" --certificate-identity "$ID" --certificate-oidc-issuer "$ISS"
cosign verify-attestation "$IMG" --type spdxjson --certificate-identity "$ID" \
  --certificate-oidc-issuer "$ISS" | jq -r .payload | base64 -d | jq .predicate > sbom.spdx.json
gh attestation verify "oci://$IMG" --owner Neutrino-Engine   # build provenance
```

Find the digest a pod runs with
`kubectl -n neutrino get pod <pod> -o jsonpath='{.status.containerStatuses[*].imageID}'`.

### AKS admission (neutrino-k8s — another stream's files)

Signing is only useful if the cluster refuses what is not signed. Plan for
`neutrino-k8s`, in order:

1. Install Ratify (`ratify` Helm chart, with the Gatekeeper it depends on) in audit
   mode. Ratify reads the cosign signature and the attestations as OCI referrers
   straight from ACR; no extra storage.
2. One `Verifier` per kind: `cosign` keyless with `certificateIdentity` =
   `https://github.com/Neutrino-Engine/<repo>/.github/workflows/deploy-prod.yml@refs/heads/release-cmd`
   and issuer `https://token.actions.githubusercontent.com` — one entry per
   service repo, not a wildcard; `sbom` verifier on the `spdxjson` attestation.
3. A Gatekeeper constraint scoped to namespace `neutrino` and `crneutrinoprodcin001.azurecr.io/*`.
   Start as `enforcementAction: dryrun`, read the audit violations for one full
   release, then flip to `deny`.
4. Platform images that are not built by us (MinIO, Temporal, OpenFGA) are
   exempt by image-name allowlist, pinned by digest in their manifests instead.

Until step 3 is `deny`, the verification step inside `deploy-prod.yml` is the only
gate, and it only covers images deployed through that workflow.

## 4. Base image pins

Every `FROM`, `COPY --from=<image>` and `# syntax=` line is pinned
`tag@sha256:<digest>` with a comment carrying the tag. `pr.yml`'s `pins` job fails
on any unpinned image or any action not pinned by a full commit SHA. To bump:

```sh
docker buildx imagetools inspect python:3.12-slim --format '{{.Manifest.Digest}}'
```

and update tag and digest together. The digest is the multi-arch index digest, so
it stays valid for `linux/amd64` and `linux/arm64` builds alike.
