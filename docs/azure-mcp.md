# Azure MCP Server transcripts

Azure MCP Server 3.0.0 is connected to the development agent as a local stdio server in **read-only** mode. It exposes 16 service namespaces: subscription, group, quota, foundryextensions, cosmos, monitor, applicationinsights, eventhubs, keyvault, containerapps, acr, role, signalr, bicepschema, pricing and get_azure_bestpractices. Provisioning itself goes through `azd` and Bicep; Azure MCP is used to inspect and verify what was provisioned.

These are real calls made while building Proofline. Outputs are trimmed; subscription and principal ids are omitted.

## 21 October 2026: verify the first `azd up`

`azd up` provisioned `rg-proofline-dev` in East US 2 in 4 min 3 s. Every check below then ran through Azure MCP.

| # | Tool and command | Purpose | Result |
|---|---|---|---|
| 1 | `group_resource_list` on `rg-proofline-dev` | Everything the Bicep declares exists | 13 resources: Foundry account and `proofline` project, managed identity, Web PubSub, Log Analytics, Event Hubs, Cosmos DB, Container Registry, Static Web App, Key Vault, Application Insights, Container Apps environment, Container App |
| 2 | `cosmos` › `cosmos_list` on database `proofline` | Ledger containers from spec §11.3 | 11 containers: events, metrics, cases, hypotheses, evidence_sets, dependencies, cards, cues, audit, eval_runs, leases |
| 3 | `foundryextensions` › `openai_models-list` | Model deployment is ready | `gpt-5-mini` version 2025-08-07, `provisioningState: Succeeded` |
| 4 | `role` › `role_assignment_list` at resource-group scope | Key-less access is wired | 11 assignments. App identity: AcrPull, Key Vault Secrets User, Azure Event Hubs Data Owner, Web PubSub Service Owner, Cognitive Services OpenAI User, Foundry User. Developer: Key Vault Secrets Officer, Azure Event Hubs Data Owner, Web PubSub Service Owner, Cognitive Services OpenAI User, Foundry User |
| 5 | `foundryextensions` › `openai_chat-completions-create` with Entra ID auth | The model answers with local keys disabled | `"proofline ok"`, 13 prompt and 76 completion tokens |
| 6 | `pricing` › `pricing_get` for gpt-5-mini in eastus2 | Confirm token prices before the first paid call | **Failed.** Azure MCP 3.0.0 rejects the `AI + Machine Learning` service family that the price API returns. Fallback: the same public Retail Prices API queried directly |

Call 5, request and trimmed response:

```json
{"command": "foundryextensions_openai_chat-completions-create",
 "parameters": {"resource-name": "ais-…", "resource-group": "rg-proofline-dev",
                "deployment": "gpt-5-mini", "auth-method": "credential",
                "message-array": "[{\"role\":\"user\",\"content\":\"Reply with exactly: proofline ok\"}]"}}

{"status": 200, "results": {"result": {"model": "gpt-5-mini",
  "choices": [{"message": {"role": "assistant", "content": "proofline ok"}, "finish_reason": "Stop"}],
  "usage": {"prompt_tokens": 13, "completion_tokens": 76, "total_tokens": 89}}}}
```

Checks outside the exposed namespaces ran with `az`: the subscription budget ($200 a month, alert at 60%), the Cosmos data-plane role assignments (Built-in Data Contributor for the app identity and the developer), local auth disabled on Cosmos DB, Event Hubs and Foundry, and both public endpoints answering HTTP 200.
