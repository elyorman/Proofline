// Proofline infrastructure: one resource group per azd environment, plus a
// subscription budget. Region and environment name come from .azure/<env>/.env.
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('azd environment name; names the resource group and seeds resource names')
param environmentName string

@minLength(1)
@description('Primary region for every resource')
param location string

@description('Object id of the developer running azd; gets data-plane roles for local dev')
param principalId string = ''

@minLength(3)
@description('Where budget alerts are emailed (kept in the local azd env, not in code)')
param budgetContactEmail string

@description('Monthly budget in the billing currency (KRW for this subscription); alerts at 60%')
param budgetAmount int = 150000

@description('First day of the budget period; budgets need a fixed start date')
param budgetStartDate string = '2026-10-01'

var tags = { 'azd-env-name': environmentName }
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    principalId: principalId
  }
}

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'budget-${environmentName}'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStartDate }
    notifications: {
      actual60: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 60
        thresholdType: 'Actual'
        contactEmails: [budgetContactEmail]
        contactRoles: ['Owner']
      }
    }
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CLIENT_ID string = resources.outputs.identityClientId
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryLoginServer
output AZURE_COSMOS_ENDPOINT string = resources.outputs.cosmosEndpoint
output AZURE_COSMOS_DATABASE string = resources.outputs.cosmosDatabase
output AZURE_EVENTHUBS_NAMESPACE string = resources.outputs.eventHubsHost
output AZURE_EVENTHUB_NAME string = resources.outputs.eventHubName
output AZURE_WEBPUBSUB_ENDPOINT string = resources.outputs.webPubSubEndpoint
output AZURE_KEY_VAULT_ENDPOINT string = resources.outputs.keyVaultEndpoint
output AZURE_FOUNDRY_ENDPOINT string = resources.outputs.foundryEndpoint
output AZURE_FOUNDRY_PROJECT_ENDPOINT string = resources.outputs.foundryProjectEndpoint
output AZURE_OPENAI_DEPLOYMENT string = resources.outputs.modelDeployment
// The Verifier runs on the agents' deployment: measured against Phi-4 on seeded false claims it
// caught as much and rejected no sound card (spec §15).
output AZURE_VERIFIER_DEPLOYMENT string = resources.outputs.modelDeployment
output APPLICATIONINSIGHTS_CONNECTION_STRING string = resources.outputs.appInsightsConnectionString
output API_URL string = resources.outputs.apiUrl
output WEB_URL string = resources.outputs.webUrl
