## What this demo touched

- **No real data.** Every claim here is synthetic and was built from public CMS manual rules. There is no PHI, no PII, and no CMS system access.
- **Nothing leaves this app.** The page loads only from its own server. "Run it live" runs the COBOL and Python programs on the demo machine and writes a new timestamped folder. Saved evidence is never overwritten.
- **Humans stay in control.** Devin's work arrives as pull requests that a person reviews. Nothing in this demo was merged without the owner saying so.
- **No new third-party code.** The Python migration uses only the Python standard library (`sys`, `dataclasses`, `typing`), so there is no new package supply chain to vet.

## Platform posture (as published, checked 17 Oct 2026)

| Topic | What is published | Source |
|---|---|---|
| FedRAMP | **Devin Cloud: FedRAMP High "In Process"**, listed on the FedRAMP Marketplace (Class D High, agency path). Devin Desktop and Devin CLI: FedRAMP High authorized. Devin Cloud for IL4 / IL5 / ITAR: in process. | [Devin federal compliance](https://docs.devin.ai/federal/compliance), [FedRAMP Marketplace](https://www.fedramp.gov/marketplace/products/FR2627211780/), [Cognition blog](https://cognition.com/blog/devin-fedramp-high-in-process) |
| Audits | SOC 2 Type II since September 2024 (data security, privacy, processing integrity, confidentiality, availability). | [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Trust Center](https://trust.cognition.ai) |
| Training on your code | Enterprise: Cognition never trains on your data without your express prior written consent. On paid plans, opting out also turns on zero data retention with model providers. | [Security FAQ](https://docs.devin.ai/admin/security) |
| Zero data retention | ZDR is on for Devin Desktop and CLI in federal deployments. Commercial: on with model providers once you opt out of training. | [Devin federal compliance](https://docs.devin.ai/federal/compliance), [Security FAQ](https://docs.devin.ai/admin/security) |
| Where it runs | Customer Dedicated Deployment: a single-tenant VPC, connected to your network over AWS PrivateLink or IPSec. Customer data stays inside your tenant. | [Deployment options](https://docs.devin.ai/enterprise/deployment/overview) |
| Encryption and keys | Encrypted in transit and at rest; keys in AWS KMS. Customer Managed Keys are available (Enterprise Assured). | [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security), [Customer managed keys](https://docs.devin.ai/enterprise/security-access/security/customer-managed-keys) |
| Access and audit | SSO via SAML, IdP groups, role-based access and custom roles, enterprise audit-log API, AI guardrails (log, warn or block), secrets manager. Repository access is limited to the repos you select. | [SAML SSO](https://docs.devin.ai/enterprise/security-access/sso/saml), [Custom roles](https://docs.devin.ai/enterprise/security-access/custom-roles), [Audit logs](https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs), [AI guardrails](https://docs.devin.ai/enterprise/features/ai-guardrails) |
| Amazon Bedrock (AWS-published) | Bedrock does not share prompts or outputs with model providers, and neither AWS nor providers train on them. Model providers have no access to the deployment accounts. A zero-retention mode (`none`) is available; some models keep abuse-detection data for up to 30 days. | [Bedrock data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html), [Bedrock data retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html), [AWS re:Post](https://repost.aws/knowledge-center/amazon-bedrock-model-data-use) |
| Your output | Code and work product Devin produces belong to you. | [Enterprise security](https://docs.devin.ai/enterprise/security-access/security/enterprise-security) |

## Questions we expect, and our answers

| Who asks | Question | Answer |
|---|---|---|
| Security | Is Devin FedRAMP authorized? | Devin Desktop and Devin CLI are FedRAMP High authorized. Devin Cloud, the autonomous agent shown here, is FedRAMP High **In Process**, not yet authorized. **Confirm the timeline with Cognition.** |
| Security | Will our code or claims data train someone's model? | Not on Enterprise without your written consent. On Bedrock, AWS and model providers do not train on inputs or outputs. |
| Security | Can we have zero data retention? | Yes. It is on in federal deployments of Desktop and CLI, and available commercially with model providers. **Confirm the exact settings for a CMS deployment with Cognition.** |
| Security | Does the model inference for a CMS deployment run on Bedrock, in which region, and in GovCloud? | Not answered in public docs. **Confirm with Cognition.** |
| Security | Is there a HIPAA BAA, and can PHI be used? | Not answered in public docs. **Confirm with Cognition.** Until then, run pilots on synthetic data, as this demo does. |
| Security | Can Devin reach production or merge on its own? | You decide what it can reach. It works on branches and opens PRs, and branch protection plus required human review stop it from merging. Cognition's docs recommend code review and branch protection. |
| Security | How do you handle secrets? | A secrets manager, scoped per organization or repository. No credentials are stored in code. |
| Security | What is logged? | Every session keeps a full timeline of what Devin did. Enterprise admins also have an audit-log API and guardrail events. |
| CIO | Where would the data physically live? | In a dedicated single-tenant deployment, inside your own tenant, reached over PrivateLink. |
| CIO | What happens to our data if we stop? | Cognition keeps data only for the length of the customer relationship, unless agreed otherwise. |
| CIO | Are we locked in? | The output is plain, standard-library Python plus docs and tests that you own. Nothing in it needs Devin to run. |
| VP Eng | How do we know the migration is right? | The expected answers were written from the CMS manual before any Python existed. COBOL and Python were compared claim by claim with a strict verifier, and every result is a raw file you can open. |
| VP Eng | What if Devin makes mistakes? | It does sometimes, and Cognition's docs say so. In this demo Devin logged and fixed its own mistakes (screen 4, "Corrections"). That is why the tests and the human review gate exist. |
| VP Eng | Does this prove complete Medicare correctness? | No. It proves the old and new programs agree on every tested claim and on the published CMS examples. It does not prove complete production equivalence. |
| CIO | How much time or money does this save? | We make no claim from this demo; human review time was not measured. |
