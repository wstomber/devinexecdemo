## The idea

Repeat this demo on one real, low-risk CMS legacy system in four weeks, with the security team setting the rules first and trying to break them in the middle. Synthetic or de-identified data only.

## Four weeks

| Week | What happens | Security's role | Done when |
|---|---|---|---|
| 1 · Guardrails before code | Pick one low-risk legacy system. Choose the deployment: Devin Desktop / CLI (FedRAMP High authorized today), or a dedicated deployment / Outposts for the autonomous agent. Connect SSO and roles, give Devin access to only the pilot repos, turn on a default-deny network profile. Agree the success measures. | Writes the network allowlist and security profile; signs off before any code is touched. | Security sign-off; success measures written down. |
| 2 · This demo, on their code | Devin explains and documents the old code (DeepWiki), records today's behaviour as the baseline, writes tests from the policy manual, then migrates one small slice and proves old and new match. | Reviews every pull request alongside engineering. | One slice migrated with 0 mismatches on the agreed test data. |
| 3 · Widen it, and try to break it | Engineers hand Devin real backlog tickets on the migrated code. | Red-teams it: plants misleading instructions in files, checks the network and audit logs, confirms nothing leaves the allowlist. | Red-team report; audit logs reviewed. |
| 4 · Measure and decide | Read out the results. | Presents the security findings and what an expanded rollout would need. | Go / no-go, plus the path to a wider authorization. |

## What we measure

- **Correctness:** share of tested claims where old and new pay exactly the same.
- **Quality:** share of Devin's pull requests accepted, and how many review rounds they took.
- **Effort:** engineer hours spent reviewing and steering, measured during the pilot, not estimated.
- **Knowledge:** whether a new engineer can explain the old module using only the generated docs.
- **Security:** red-team findings, and any blocked or unexpected network attempts in the logs.

## What a pilot needs from CMS

- One legacy system with synthetic or de-identified test data.
- A small engineering team (two or three people) to review pull requests.
- A security engineer for weeks 1 and 3.
- Decisions on deployment model, data handling and contract terms (including any BAA) before week 1.
