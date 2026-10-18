## What this demo touched

- **No real data.** Every claim here is synthetic and was built from public CMS manual rules. There is no PHI, no PII, and no CMS system access.
- **Nothing leaves this app.** The page loads only from its own server. "Run COBOL vs Python now" runs the COBOL and Python programs on the demo machine and writes a new timestamped folder. Saved evidence is never overwritten.
- **Humans stay in control.** Devin's work arrives as pull requests that a person reviews. Nothing in this demo was merged without the owner saying so.
- **No new third-party code.** The Python migration uses only the Python standard library (`sys`, `dataclasses`, `typing`), so there is no new package supply chain to vet.

## How Devin protects a CMS deployment (as published, checked 17 Oct 2026)

| Layer | Control | Source |
|---|---|---|
| Architecture | Two parts: a stateless "brain" in Cognition's cloud, and an isolated VM (the "Devbox") per session where code actually runs. Sessions are isolated from each other. | [Devin's architecture](https://docs.devin.ai/enterprise/deployment/overview#devins-architecture) |
| Where it runs | **Customer Dedicated Deployment:** your own single-tenant VPC. **Outposts:** sessions run on machines you operate, inside your network; only inference and planning stay in Devin's cloud. | [Deployment options](https://docs.devin.ai/enterprise/deployment/overview), [Outposts](https://docs.devin.ai/cloud/outposts/overview) |
| Network | **Devin Connect:** a default-deny proxy inside your network, reached over AWS PrivateLink or an outbound-only tunnel. Nothing is opened inbound. Your TLS stays end-to-end, DNS stays on your resolvers, and every connection is audit-logged. | [Devin Connect](https://docs.devin.ai/enterprise/deployment/devin-connect) |
| Session guardrails | **Security profiles:** a per-session network allowlist enforced at the VM, read-only git access, an MCP tool allowlist, and GitHub token removal. A **mandatory** profile set by the enterprise can only be tightened below it, never loosened, even mid-session. | [Security profiles](https://docs.devin.ai/product-guides/security-profiles) |
| Identity | SSO (SAML / OIDC), custom roles, enterprise IP access lists. Short-lived OIDC workload identity to your cloud, so no static keys are stored in Devin. Repository access is limited to the repos you select. | [SAML SSO](https://docs.devin.ai/enterprise/security-access/sso/saml), [Custom roles](https://docs.devin.ai/enterprise/security-access/custom-roles), [IP access lists](https://docs.devin.ai/enterprise/security-access/ip-access-lists), [OIDC](https://docs.devin.ai/product-guides/oidc) |
| Data | Encrypted in transit and at rest (AWS KMS), with customer-managed keys available. Enterprise data is never used for training without written consent. Zero data retention with model providers. Data is kept only for the length of the contract. | [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Customer managed keys](https://docs.devin.ai/enterprise/security-access/security/customer-managed-keys), [Security FAQ](https://docs.devin.ai/admin/security) |
| Oversight | A full timeline of every session, an enterprise audit-log API, and AI guardrails (log, warn or block). Changes arrive as pull requests, so branch protection and required human review stop Devin from merging on its own. | [Audit logs](https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs), [AI guardrails](https://docs.devin.ai/enterprise/features/ai-guardrails), [Security FAQ](https://docs.devin.ai/admin/security) |
| Assurance | SOC 2 Type II since September 2024. **FedRAMP High:** Devin Desktop and CLI authorized (Desktop's FedRAMP deployment runs on AWS GovCloud); **Devin Cloud, the agent in this demo, is "In Process".** Vulnerability reports go to security@cognition.ai, and enterprise customers are notified of incidents per their agreement. | [Federal compliance](https://docs.devin.ai/federal/compliance), [FedRAMP Marketplace](https://www.fedramp.gov/marketplace/products/FR2627211780/), [Desktop FedRAMP admin guide](https://docs.devin.ai/desktop/security/security-admin-guide), [Trust Center](https://trust.cognition.ai) |

## Model inference and data retention

- **Zero data retention with the model labs:** Cognition has zero-data-retention agreements with its model providers. On paid plans, opting out of training also turns on ZDR with those providers. [Security FAQ](https://docs.devin.ai/admin/security)
- **Federal deployments:** ZDR is on for every Devin Desktop and Devin CLI feature. [Federal compliance](https://docs.devin.ai/federal/compliance)
- **Keeping execution in your network:** with **Outposts**, sessions run on machines you operate, so the code and the commands Devin runs stay inside your network; only planning and inference go to Devin's cloud. [Outposts](https://docs.devin.ai/cloud/outposts/overview)

## Questions we expect, and our answers

| Who asks | Question | Answer |
|---|---|---|
| Security | Is Devin FedRAMP authorized? | Devin Desktop and Devin CLI are FedRAMP High authorized. Devin Cloud, the autonomous agent shown here, is FedRAMP High **In Process**, not yet authorized. **Confirm the timeline with Cognition.** |
| Security | Will our code or claims data train someone's model? | Not on Enterprise without your written consent, and Cognition has zero-data-retention agreements with its model providers. |
| Security | Can we have zero data retention? | Yes. It is on in federal deployments of Desktop and CLI, and available commercially with model providers. **Confirm the exact settings for a CMS deployment with Cognition.** |
| Security | Where does the model inference run? | With Cognition's model providers, under zero-data-retention agreements. With Outposts, everything else (your code, builds and tests) runs on your own machines. |
| Security | Can Devin reach anything on our network it wants? | No. With a mandatory security profile and Devin Connect, it reaches only the hosts you allowlist, and every connection is logged. |
| Security | Can code execution stay inside our network? | Yes. With Outposts, sessions run on machines you operate; only inference and planning stay in Devin's cloud. |
| Security | Can Devin touch PII or PHI? Is there a HIPAA BAA? | Cognition's public docs don't say either way. **Confirm with Cognition.** Until it is in the contract, keep pilots on synthetic or de-identified data, as this demo does. |
| Security | Can Devin reach production or merge on its own? | You decide what it can reach. It works on branches and opens PRs, and branch protection plus required human review stop it from merging. Cognition's docs recommend code review and branch protection. |
| Security | How do you handle secrets? | A secrets manager scoped per organization or repository, and short-lived OIDC tokens for cloud access instead of static keys. |
| Security | What is logged? | Every session keeps a full timeline of what Devin did. Enterprise admins also have an audit-log API and guardrail events. |
| CIO | Where would the data physically live? | In a dedicated single-tenant deployment, inside your own tenant, reached over PrivateLink. |
| CIO | What happens to our data if we stop? | Cognition keeps data only for the length of the customer relationship, unless agreed otherwise. |
| CIO | Are we locked in? | The output is plain, standard-library Python plus docs and tests that you own. Nothing in it needs Devin to run. |
| VP Eng | How do we know the migration is right? | The expected answers were written from the CMS manual before any Python existed. COBOL and Python were compared claim by claim with a strict verifier, and every result is a raw file you can open. |
| VP Eng | What if Devin makes mistakes? | It does sometimes, and Cognition's docs say so. In this demo Devin logged and fixed its own mistakes (screen 4, "Corrections"). That is why the tests and the human review gate exist. |
| VP Eng | Does this prove complete Medicare correctness? | No. It proves the old and new programs agree on every tested claim and on the published CMS examples. It does not prove complete production equivalence. |
| CIO | How much time or money does this save? | We make no claim from this demo; human review time was not measured. |
| Security | What if a file or web page tricks Devin into doing something harmful (prompt injection)? | A security profile limits which hosts it can reach and which tools it can use, so an injected instruction can't send data anywhere you haven't allowed. Every change still arrives as a pull request a person reviews. |
| Security | Who checks the open-source packages Devin installs? | The same people who check any engineer's: the dependency is visible in the pull request, and the network allowlist decides which package sources it can reach at all. This migration added none. |
| Security | Can the audit logs go into our SIEM? | Enterprise admins have an audit-log API, so events can be pulled into your monitoring tools. |
| Security | How do we shut it off in an emergency? | Admins can stop any session, and revoking the API key or service user cuts off automated starts. Incidents are reported per the enterprise agreement. |
| Security | When a pilot ends, what happens to our data? | Cognition keeps data only for the length of the customer relationship unless agreed otherwise; ask for deletion at the end of the pilot. |
