Answers below are drawn from Cognition's published documentation (checked 20 Oct 2026); each one links to its source. Where public documentation is silent, the answer says **Confirm with Cognition**.

## Compliance and assurance

### Is Devin FedRAMP authorized?
Devin Desktop and Devin CLI are FedRAMP High authorized; Desktop's FedRAMP deployment runs on AWS GovCloud. Devin Cloud, the autonomous agent shown in this demo, is FedRAMP High **In Process**, not yet authorized. **Confirm the timeline with Cognition.**

Sources: [Federal compliance](https://docs.devin.ai/federal/compliance), [FedRAMP Marketplace](https://www.fedramp.gov/marketplace/products/FR2627211780/), [Desktop FedRAMP admin guide](https://docs.devin.ai/desktop/security/security-admin-guide)

### What other attestations does Cognition hold?
SOC 2 Type II, since September 2024. Reports and policies are available through the Trust Center.

Sources: [Trust Center](https://trust.cognition.ai), [Federal compliance](https://docs.devin.ai/federal/compliance)

### Can Devin handle PII or PHI? Is a HIPAA BAA available?
Cognition's public documentation does not address either. **Confirm with Cognition.** Until it is covered by contract, pilots should use synthetic or de-identified data, as this demonstration does.

## Architecture and deployment

### How is Devin built?
Two parts: a stateless "brain" in Cognition's cloud that plans and calls the model, and an isolated virtual machine (the "Devbox") for each session, where code is checked out, built and tested. Sessions are isolated from one another.

Source: [Devin's architecture](https://docs.devin.ai/enterprise/deployment/overview#devins-architecture)

### What deployment options are there?
- **Multi-tenant cloud:** the standard Devin service.
- **Customer Dedicated Deployment:** a single-tenant VPC for one customer, reachable over AWS PrivateLink.
- **Outposts:** sessions run on machines you operate, inside your network; only planning and model inference stay in Devin's cloud.


Sources: [Deployment options](https://docs.devin.ai/enterprise/deployment/overview), [Outposts](https://docs.devin.ai/cloud/outposts/overview)

### Can code execution stay inside our network?
Yes. With Outposts, your code, builds, tests and the commands Devin runs stay on machines you operate. Only planning and inference go to Devin's cloud.

Source: [Outposts](https://docs.devin.ai/cloud/outposts/overview)

### Where does model inference run?
With Cognition's model providers. On paid plans, opting out of training turns on zero data retention with those providers. **Confirm the providers and settings for a CMS deployment with Cognition.**

Source: [Security FAQ](https://docs.devin.ai/admin/security)

### Does the migrated code depend on Devin to run?
No. Devin's output is ordinary code, tests and documentation committed to your repository. The Python in this demo uses only the Python standard library.

## Data handling

### Will our code or data be used to train a model?
Not on Enterprise plans without your written consent. On paid plans, opting out of training also turns on zero data retention with the model providers.

Sources: [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Security FAQ](https://docs.devin.ai/admin/security)

### Is zero data retention (ZDR) available?
Yes. Cognition has ZDR agreements with its model providers, and ZDR is on for every feature of Devin Desktop and Devin CLI in federal deployments. **Confirm the exact settings for a CMS deployment with Cognition.**

Sources: [Security FAQ](https://docs.devin.ai/admin/security), [Federal compliance](https://docs.devin.ai/federal/compliance)

### How is data encrypted? Can we hold the keys?
Data is encrypted in transit and at rest, by default with Cognition-managed keys. Customer-managed keys (your own AWS KMS key) are available in the Enterprise Assured deployment.

Sources: [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Customer managed keys](https://docs.devin.ai/enterprise/security-access/security/customer-managed-keys)

### What happens to our data when a pilot or contract ends?
Cognition keeps data only for the length of the customer relationship unless agreed otherwise. Request deletion at the end of a pilot.

Source: [Security FAQ](https://docs.devin.ai/admin/security)

## Network and access controls

### What can Devin reach on our network?
Only what you allow. **Devin Connect** is a default-deny proxy that runs inside your network, reached over AWS PrivateLink or an outbound-only tunnel, so nothing is opened inbound. Your TLS stays end to end, DNS stays on your resolvers, and every connection is audit-logged.

Source: [Devin Connect](https://docs.devin.ai/enterprise/deployment/devin-connect)

### How are individual sessions restricted?
**Security profiles** set a per-session network allowlist enforced at the VM, read-only git access, an allowlist of MCP tools, and removal of GitHub tokens. An administrator can make a profile mandatory; sessions can then only tighten it, never loosen it, even mid-session.

Source: [Security profiles](https://docs.devin.ai/product-guides/security-profiles)

### What stops a prompt-injection attack, such as a planted file telling Devin to send data out?
The backstop is the network and tool allowlists: even if an instruction fools the agent, it cannot reach hosts or tools you have not allowed. AI guardrails add detection on top (log, warn or block). Every change still arrives as a pull request that a person reviews.

Sources: [Security profiles](https://docs.devin.ai/product-guides/security-profiles), [AI guardrails](https://docs.devin.ai/enterprise/features/ai-guardrails)

### Can Devin change production or merge code on its own?
You decide what it can reach. Devin works on branches and opens pull requests; branch protection and required human review stop it from merging. Cognition's documentation recommends both.

Source: [Security FAQ](https://docs.devin.ai/admin/security)

### Who checks the open-source packages Devin adds?
The same review that checks any engineer's work: new dependencies show up in the pull request, and the network allowlist decides which package sources Devin can reach at all. This migration added none.

## Identity, credentials and secrets

### How do users sign in, and who can do what?
SSO with SAML or OIDC, custom roles, and enterprise IP access lists.

Sources: [SAML SSO](https://docs.devin.ai/enterprise/security-access/sso/saml), [Custom roles](https://docs.devin.ai/enterprise/security-access/custom-roles), [IP access lists](https://docs.devin.ai/enterprise/security-access/ip-access-lists)

### How does Devin get credentials, and how are they scoped?
Cloud access uses short-lived OIDC workload identity, so no static cloud keys are stored in Devin. Other secrets live in a secrets manager scoped per organization or repository, and repository access is limited to the repositories you select.

Sources: [OIDC](https://docs.devin.ai/product-guides/oidc), [Secrets](https://docs.devin.ai/product-guides/secrets), [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security)

## Oversight, audit and incident response

### What is logged?
Every session keeps a full timeline of what Devin did. Enterprise administrators also have an audit-log API and AI-guardrail events. Devin Connect logs every network connection.

Sources: [Audit logs](https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs), [AI guardrails](https://docs.devin.ai/enterprise/features/ai-guardrails), [Devin Connect](https://docs.devin.ai/enterprise/deployment/devin-connect)

### Can audit events go into our SIEM?
The enterprise audit-log API lets your monitoring tools pull events. **Confirm supported formats and streaming options with Cognition.**

Source: [Audit logs](https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs)

### How do we stop Devin in an emergency?
Administrators can stop any session, and revoking the API key or service user stops automated starts.

### How are vulnerabilities and incidents handled?
Report vulnerabilities and security incidents to security@cognition.ai. How and when Cognition notifies customers of an incident is not in the public documentation. **Confirm with Cognition.**

Source: [Security FAQ](https://docs.devin.ai/admin/security)

## About this demonstration

### Did this demo use real CMS or beneficiary data?
No. Every claim and every Common Working File record is synthetic, built from public CMS manual rules. There is no PHI, no PII and no access to CMS systems.

### How do we know the migration is correct?
Expected answers were written from the CMS manuals before any Python existed. COBOL and Python were then compared claim by claim on calculated payment, CWF decision and released amount, and every result is a raw file you can open. This shows the two programs agree on every tested claim and on the published CMS examples; it does not prove complete production equivalence.
