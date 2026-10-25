// Everything inside the environment's resource group. No keys: local auth is
// disabled wherever the service allows it, and access is by role for the app's
// managed identity and for the developer running azd.

param location string
param tags object

@minLength(13)
@maxLength(13)
@description('uniqueString() output; suffixes every resource name')
param resourceToken string

@description('Developer object id for local-dev data-plane roles; empty skips them')
param principalId string = ''

@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('gpt-5-mini capacity in thousands of tokens per minute (trial quota is 500)')
param modelCapacity int = 100

@description('Thousands of tokens per minute for the verifier model; the Free Trial grants 20')
param verifierCapacity int = 20

@description('The API image azd last deployed; empty keeps the placeholder until the first deploy')
param apiImage string = ''

@description('Model tokens all viewers\' live questions may spend in a UTC day (about 300 full investigations)')
param dailyTokens int = 15000000

// Built-in role definition ids
var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  keyVaultSecretsOfficer: 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
  eventHubsDataOwner: 'f526a384-b230-433a-b45c-95f59c4a2dec'
  webPubSubServiceOwner: '12cf5a90-567b-43ae-8102-96cf46c7d9b4'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}
var cosmosDataContributor = '00000000-0000-0000-0000-000000000002'

// Ledger containers (spec §11.3). Partitioned by match, except the dependency
// index (by event) and match-independent records (by id).
var ledgerContainers = [
  { name: 'events', partitionKey: '/match_id' }
  { name: 'metrics', partitionKey: '/match_id' }
  { name: 'cases', partitionKey: '/match_id' }
  { name: 'hypotheses', partitionKey: '/match_id' }
  { name: 'evidence_sets', partitionKey: '/match_id' }
  { name: 'dependencies', partitionKey: '/event_id' }
  { name: 'cards', partitionKey: '/match_id' }
  { name: 'cues', partitionKey: '/match_id' }
  { name: 'audit', partitionKey: '/match_id' }
  { name: 'eval_runs', partitionKey: '/id' }
  { name: 'leases', partitionKey: '/id' }
]

// --- identity and observability ----------------------------------------------

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-${resourceToken}'
  location: location
  tags: tags
}

resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'log-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${resourceToken}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: 'kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
  }
}

// --- compute -------------------------------------------------------------------

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'cr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource containerEnv 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// The live API (surfaces/api): typed questions answered by the agents on Foundry, written to
// the ledger, traced to Application Insights. One replica, always on: its jobs and caps live
// in memory, and a viewer's question should not wait for a cold start.
resource api 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-api-${resourceToken}'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: { external: true, targetPort: 8000 }
      registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: empty(apiImage) ? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' : apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'AZURE_FOUNDRY_PROJECT_ENDPOINT', value: 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${foundryProject.name}' }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: modelDeployment.name }
            { name: 'AZURE_VERIFIER_DEPLOYMENT', value: modelDeployment.name }
            { name: 'AZURE_COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
            { name: 'AZURE_COSMOS_DATABASE', value: ledger.name }
            { name: 'PROOFLINE_WEB_ORIGINS', value: 'https://${web.properties.defaultHostname},http://localhost:5173,http://localhost:4173' }
            { name: 'PROOFLINE_DAILY_TOKENS', value: string(dailyTokens) }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

resource web 'Microsoft.Web/staticSites@2024-04-01' = {
  name: 'stapp-${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

// --- data and messaging ------------------------------------------------------

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' = {
  name: 'cosmos-${resourceToken}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: true
    disableLocalAuth: true
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0, isZoneRedundant: false }]
  }
}

// 1000 RU/s shared across the ledger: exactly the free-tier allowance.
resource ledger 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-04-15' = {
  parent: cosmos
  name: 'proofline'
  properties: {
    resource: { id: 'proofline' }
    options: { throughput: 1000 }
  }
}

resource ledgerContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = [
  for c in ledgerContainers: {
    parent: ledger
    name: c.name
    properties: {
      resource: {
        id: c.name
        partitionKey: { paths: [c.partitionKey], kind: 'Hash' }
      }
    }
  }
]

resource eventHubs 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evhns-${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic', tier: 'Basic', capacity: 1 }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
  }
}

resource matchEvents 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubs
  name: 'match-events'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}

resource webPubSub 'Microsoft.SignalRService/webPubSub@2024-03-01' = {
  name: 'wps-${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Free_F1', tier: 'Free', capacity: 1 }
  properties: { disableLocalAuth: true }
}

// --- Microsoft Foundry -------------------------------------------------------

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'ais-${resourceToken}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: 'ais-${resourceToken}'
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: 'proofline'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

// The only gpt-5 model with Free Trial quota. The verifier's non-OpenAI model
// is added at the Verifier step, chosen by catch rate on seeded false claims.
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: 'gpt-5-mini'
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-5-mini', version: '2025-08-07' }
  }
  dependsOn: [foundryProject] // the account accepts one change at a time
}

// Phi-4 was the Verifier's model, a different family from the agents'; it is kept deployed but
// the Verifier now runs on gpt-5-mini, which on seeded false claims caught as much and rejected
// no sound card (spec §15). Why Phi-4 was the choice of a second family: a chat model, not a
// reasoning one:
// DeepSeek-V3.2-Speciale thought for minutes and left one reply in nine without an answer,
// against a full-lane budget of 25 s. Microsoft's Phi-4 needs no Marketplace plan, which a
// Free Trial cannot buy, and is served past 10 November.
resource verifierDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: 'Phi-4'
  sku: { name: 'GlobalStandard', capacity: verifierCapacity }
  properties: {
    model: { format: 'Microsoft', name: 'Phi-4', version: '7' }
  }
  dependsOn: [modelDeployment] // one change at a time
}

// --- access --------------------------------------------------------------------

var appRoles = [
  roles.acrPull
  roles.keyVaultSecretsUser
  roles.eventHubsDataOwner
  roles.webPubSubServiceOwner
  roles.openAiUser
  roles.foundryUser
]
var developerRoles = [
  roles.keyVaultSecretsOfficer
  roles.eventHubsDataOwner
  roles.webPubSubServiceOwner
  roles.openAiUser
  roles.foundryUser
]

// Scoped to the resource group, which holds exactly one of each resource.
resource appRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in appRoles: {
    name: guid(resourceGroup().id, identity.id, role)
    properties: {
      principalId: identity.properties.principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    }
  }
]

resource developerRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in (empty(principalId) ? [] : developerRoles): {
    name: guid(resourceGroup().id, principalId, role)
    properties: {
      principalId: principalId
      principalType: principalType
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    }
  }
]

// Cosmos data-plane access uses Cosmos's own role assignments, not Azure RBAC.
resource cosmosAppAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-04-15' = {
  parent: cosmos
  name: guid(cosmos.id, identity.id, cosmosDataContributor)
  properties: {
    principalId: identity.properties.principalId
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributor}'
    scope: cosmos.id
  }
}

resource cosmosDeveloperAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-04-15' = if (!empty(principalId)) {
  parent: cosmos
  name: guid(cosmos.id, principalId, cosmosDataContributor)
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributor}'
    scope: cosmos.id
  }
}

output identityClientId string = identity.properties.clientId
output registryLoginServer string = registry.properties.loginServer
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output cosmosDatabase string = ledger.name
output eventHubsHost string = '${eventHubs.name}.servicebus.windows.net'
output eventHubName string = matchEvents.name
output webPubSubEndpoint string = 'https://${webPubSub.properties.hostName}'
output keyVaultEndpoint string = keyVault.properties.vaultUri
output foundryEndpoint string = foundry.properties.endpoint
output foundryProjectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${foundryProject.name}'
output modelDeployment string = modelDeployment.name
output verifierDeployment string = verifierDeployment.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output webUrl string = 'https://${web.properties.defaultHostname}'
