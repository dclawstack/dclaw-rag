# Decision: defer the cloud connector — stay folder-only (E3.9)

**Status:** Decided — deferred (2026-07). Revisit only if the product adds an
explicitly cloud/enterprise tier (see the E6 enterprise-fork, currently blocked).

## Context

Tracker task E3.9 asked: build **one** read-only cloud connector (e.g. Google
Drive) **only if it does not compromise the local/private stance**; otherwise
stay folder-only and defer.

## Decision

**Do not build a cloud connector now. Stay folder-only.**

## Why

The product's differentiation is *local-first and private* — reinforced by the
work shipped alongside this task:

- **E1** — a bundled in-process LLM so answers never leave the machine, plus
  at-rest encryption for regulated users.
- **E3.8** — the local **folder connector**: watch a directory, incremental
  checksum-dedup sync, no cloud, no upload step.

A Google Drive (or any SaaS) connector would require OAuth to a third party,
network egress to enumerate and download documents, and stored refresh tokens —
each a direct contradiction of the "nothing leaves your machine" claim we make
to lawyers/therapists/clinicians/analysts. Building it would weaken the moat, not
extend it.

## The folder connector already covers the need

Users who keep documents in Drive/Dropbox/OneDrive almost always run that
provider's **desktop sync client**, which materializes those files as a normal
local folder. Pointing the folder connector (`scripts/sync_folder.py`) at that
folder gives the same "keep my cloud docs indexed" outcome **without** DClaw ever
talking to the cloud — the sync client owns the network boundary, and DClaw stays
fully local.

## When to revisit

Only if a deliberate cloud/enterprise tier is chosen (the E6 enterprise-fork —
permission-aware retrieval, SSO/SAML — is blocked on exactly that strategic
decision). A cloud connector belongs in that tier, behind clear user consent and
isolated from the local-first build, not in the private/local product.
