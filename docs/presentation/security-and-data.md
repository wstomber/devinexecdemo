Cognition's published documentation was checked on 27 Nov 2026. Product answers link to their sources. Where a detail depends on your agreement or deployment, **Confirm with Cognition**.

## Compliance and assurance

### Is Devin FedRAMP authorized?
Devin Desktop and Devin CLI are FedRAMP High authorized; Desktop's FedRAMP deployment runs on AWS GovCloud. Devin Cloud, the autonomous agent shown in this demo, is FedRAMP High **In Process**, not yet authorized. **Confirm the timeline with Cognition.**

Sources: [Federal compliance](https://docs.devin.ai/federal/compliance), [FedRAMP Marketplace](https://www.fedramp.gov/marketplace/products/FR2627211780/), [Desktop FedRAMP admin guide](https://docs.devin.ai/desktop/security/security-admin-guide)

### What other attestations does Cognition hold?
SOC 2 Type II, since September 2024. The Public Sector Trust Center also lists ISO/IEC 27001:2022. Reports and policies are available through the Trust Center.

Sources: [Trust Center](https://trust.cognition.ai), [Public Sector Trust Center](https://trust.cognition.ai/?product=cognitionpublicsector), [Security FAQ](https://docs.devin.ai/admin/security)

### Can Devin handle PII or PHI? Is a HIPAA BAA available?
Cognition's public documentation does not address either. **Confirm with Cognition.** Until it is covered by contract, pilots should use synthetic or de-identified data, as this demonstration does.

## Architecture and deployment

### How is Devin built?
Two parts: a stateless "brain" in Cognition's cloud that plans and calls the model, and an isolated virtual machine (the "Devbox") for each session, where code is checked out, built and tested. Sessions are isolated from one another.

Source: [Devin's architecture](https://docs.devin.ai/enterprise/deployment/overview#devin%E2%80%99s-architecture)

### What deployment options are there?
- **Multi-tenant cloud:** the standard Devin service.
- **Customer Dedicated Deployment:** a single-tenant VPC for one customer, reachable over AWS PrivateLink.
- **Outposts:** sessions run on machines you operate, inside your network; only planning and model inference stay in Devin's cloud.


Sources: [Deployment options](https://docs.devin.ai/enterprise/deployment/overview), [Outposts](https://docs.devin.ai/cloud/outposts/overview)

### Can code execution stay inside our network?
Yes. With Outposts, your code, builds, tests and the commands Devin runs stay on machines you operate. Only planning and inference go to Devin's cloud.

Source: [Outposts](https://docs.devin.ai/cloud/outposts/overview)

### Where does model inference run?
With Cognition's model providers. On paid plans, opting out of model training turns on zero data retention with those providers.

Source: [Security FAQ](https://docs.devin.ai/admin/security)

### Does the migrated code depend on Devin to run?
No. Devin's output is ordinary code, tests and documentation committed to your repository. The Python in this demo uses only the Python standard library.

## Data handling

### Will our code or data be used to train a model?
Not on Enterprise plans without your written consent. On paid plans, opting out of training also turns on zero data retention with the model providers.

Sources: [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Security FAQ](https://docs.devin.ai/admin/security)

### Is zero data retention (ZDR) available?
Yes. On paid plans, opting out of model training turns on ZDR with Cognition's model providers, and ZDR is on for every feature of Devin Desktop and Devin CLI in federal deployments. **Confirm the exact settings for a CMS deployment with Cognition.**

Sources: [Security FAQ](https://docs.devin.ai/admin/security), [Federal compliance](https://docs.devin.ai/federal/compliance)

### How is data encrypted? Can we hold the keys?
Data is encrypted in transit and at rest, by default with Cognition-managed keys. Customer-managed keys (your own AWS KMS key) are available with the Enterprise Assured deployment.

Sources: [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Customer managed keys](https://docs.devin.ai/enterprise/security-access/security/customer-managed-keys)

### What happens to our data when a pilot or contract ends?
Cognition says it retains data processed through Devin for the customer relationship unless otherwise specified. It may keep feedback and user-interaction data as long as needed. **Confirm with Cognition** when pilot data and backups are deleted under your agreement.

Source: [Security FAQ](https://docs.devin.ai/admin/security)

## Network and access controls

### What can Devin reach on our network?
**Devin Connect** is a default-deny proxy inside your network. Devin reaches it over AWS PrivateLink through an internal listener or through a tunnel the proxy opens outbound. Your application TLS stays end to end, DNS stays on your resolvers, and the proxy logs connection activity.

Source: [Devin Connect](https://docs.devin.ai/enterprise/deployment/devin-connect)

### How are individual sessions restricted?
**Security profiles** can set a session network allowlist, restrict Git to read-only, allow only selected MCP servers, and remove the GitHub CLI token. A mandatory profile sets the limit even when someone grants access during a session. Devin enforces the network allowlist on Devin-managed VMs. With Outposts, your infrastructure must enforce it.

Source: [Security profiles](https://docs.devin.ai/product-guides/security-profiles)

### What stops a prompt-injection attack, such as a planted file telling Devin to send data out?
Enforced network and MCP allowlists limit what a session can reach if it follows a malicious instruction. AI Guardrails screen incoming user messages and can log, warn or block. In this demo, a person reviews changes through a pull request.

Sources: [Security profiles](https://docs.devin.ai/product-guides/security-profiles), [AI guardrails](https://docs.devin.ai/enterprise/features/ai-guardrails)

### Can Devin change production or merge code on its own?
Devin's access depends on the credentials and network access you give it. Cognition recommends code review and branch protection. Configure required human approvals in your code host before allowing changes to merge.

Source: [Security FAQ](https://docs.devin.ai/admin/security)

### Who checks the open-source packages Devin adds?
The same review that checks any engineer's work: new dependencies show up in the pull request, and the network allowlist decides which package sources Devin can reach at all. This migration added none.

## Identity, credentials and secrets

### How do users sign in, and who can do what?
SSO with SAML or OIDC, custom roles, and enterprise IP access lists.

Sources: [SAML SSO](https://docs.devin.ai/enterprise/security-access/sso/saml), [OIDC SSO](https://docs.devin.ai/enterprise/security-access/sso/oidc), [Custom roles](https://docs.devin.ai/enterprise/security-access/custom-roles), [IP access lists](https://docs.devin.ai/enterprise/security-access/ip-access-lists)

### How does Devin get credentials, and how are they scoped?
You can configure short-lived OIDC workload identity for supported cloud services in place of static cloud keys. Devin Secrets supports organization and repository scopes. Choose which repositories Devin can access when configuring the source-control integration.

Sources: [OIDC](https://docs.devin.ai/product-guides/oidc), [Secrets](https://docs.devin.ai/product-guides/secrets), [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security)

## Oversight, audit and incident response

### What is logged?
The enterprise audit-log API lists events such as AI Guardrail violations for callers with the required permission. Devin Connect separately logs connection opens, closes and denials, including the destination.

Sources: [Audit logs](https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs), [AI guardrails](https://docs.devin.ai/enterprise/features/ai-guardrails), [Devin Connect](https://docs.devin.ai/enterprise/deployment/devin-connect)

### Can audit events go into our SIEM?
Your monitoring tools can pull paginated JSON events from the enterprise audit-log API. Devin Connect emits JSON lines to standard output when it runs without an interactive terminal, so your existing log collector can forward them. **Confirm with Cognition** which other export or streaming options are available for your deployment.

Sources: [Audit logs](https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs), [Devin Connect logging](https://docs.devin.ai/enterprise/deployment/devin-connect#logging-and-siem-integration)

### How do we stop Devin in an emergency?
An authorized administrator can manage other users' sessions and revoke the credentials used by an automated launcher. **Confirm with Cognition** which roles and controls your deployment uses to stop active sessions.

Source: [Custom roles and permissions](https://docs.devin.ai/enterprise/security-access/custom-roles)

### How are vulnerabilities and incidents handled?
Report vulnerabilities to security@cognition.ai. Cognition notifies Enterprise customers of security incidents that may affect their environments, under the reporting obligations in the customer agreement. A dedicated team responds to security incidents and will share details of its incident-response practices on request. **Confirm the notification terms for a CMS agreement with Cognition.**

Sources: [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Trust Center](https://trust.cognition.ai)

## About this demonstration

### Did this demo use real CMS or beneficiary data?
No. Every claim and every Common Working File record is synthetic, built from public CMS manual rules. There is no PHI, no PII and no access to CMS systems.

### How do we know the migration is correct?
Expected answers were written from the CMS manuals before any Python existed. COBOL and Python were then compared claim by claim on calculated payment, CWF decision and released amount, and every result is a raw file you can open. This shows the two programs agree on every tested claim and on the published CMS examples; it does not prove complete production equivalence.
