// =============================================================================
// main.bicep — Azure AI Foundry (Basic agent setup) for the Payer demo.
//
// Provisions the MINIMAL infrastructure the demo's declarative ("prompt")
// Foundry agents need:
//   * 1x Azure AI Foundry account  (Microsoft.CognitiveServices, kind=AIServices,
//                                    allowProjectManagement=true)
//   * 1x Foundry project           (accounts/projects)
//   * 1x model deployment          (gpt-4.1-mini, GlobalStandard)
//   * RBAC                         (deploying principal -> Azure AI User +
//                                    Cognitive Services User on the account)
//
// It does NOT create a capability host, Container Registry, Cosmos DB, Storage,
// or Azure AI Search. Those are only required for *container-hosted* agents or
// the "Standard" bring-your-own-data setup. The demo's agents are created via
// the Responses API (agent_framework_azure_ai.AzureAIAgentClient.create_or_update_agent),
// which only needs a project + a model deployment.
//
// Scope: subscription. Creates (or reuses) the resource group, then deploys the
// Foundry resources into it via the foundry.bicep module.
//
// Consumed by `azd provision` (see ../../azure.yaml). The module outputs are
// surfaced as azd env values; tools/deploy_data_agents.py reads
// FOUNDRY_PROJECT (= the project endpoint) from there.
// =============================================================================

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the azd environment. Drives resource naming + the resource group (rg-<name>).')
param environmentName string

@minLength(1)
@description('Primary location for all resources.')
param location string

@description('Object ID (principal ID) of the user/service principal that will RUN deploy_data_agents.py --live. Granted Azure AI User + Cognitive Services User on the Foundry account so it can create agents. Defaults to the deploying principal (azd sets AZURE_PRINCIPAL_ID).')
param deployingPrincipalId string = ''

@allowed([
  'User'
  'ServicePrincipal'
])
@description('Principal type of deployingPrincipalId. Use ServicePrincipal for CI/CD identities.')
param deployingPrincipalType string = 'User'

@description('Model to deploy for the agents.')
param modelName string = 'gpt-4.1-mini'

@description('Model version. 2025-04-14 is the GA gpt-4.1-mini in westus3.')
param modelVersion string = '2025-04-14'

@description('Model deployment SKU.')
param modelSkuName string = 'GlobalStandard'

@description('Model deployment capacity (thousands of TPM). 50 = 50K TPM; westus3 GlobalStandard gpt-4.1-mini limit is 5000.')
param modelCapacity int = 50

@description('Fabric workspace ID that hosts the published PayerAnalytics semantic model + Fabric data agents. The postprovision hook passes this to deploy_data_agents.py so the Foundry agents bind to the right Fabric workspace. azd prompts for this if not already set in the environment.')
param fabricWorkspaceId string

@description('Semantic model the agents target.')
param semanticModel string = 'PayerAnalytics'

// Deterministic, collision-resistant token for globally-unique names.
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  workload: 'fabric-payer-demo'
  component: 'foundry-agents'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module foundry 'foundry.bicep' = {
  name: 'foundry'
  scope: rg
  params: {
    location: location
    resourceToken: resourceToken
    tags: tags
    deployingPrincipalId: deployingPrincipalId
    deployingPrincipalType: deployingPrincipalType
    modelName: modelName
    modelVersion: modelVersion
    modelSkuName: modelSkuName
    modelCapacity: modelCapacity
  }
}

// ---- Outputs consumed by azd / deploy_data_agents.py -----------------------
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_AI_FOUNDRY_NAME string = foundry.outputs.accountName
output AZURE_AI_PROJECT_NAME string = foundry.outputs.projectName

// The hosted-agent client (AzureAIAgentClient) expects the *project endpoint*.
// deploy_data_agents.py reads this as FOUNDRY_PROJECT.
output AZURE_AI_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output FOUNDRY_PROJECT string = foundry.outputs.projectEndpoint
output AZURE_AI_MODEL_DEPLOYMENT_NAME string = foundry.outputs.modelDeploymentName

// Passed through to azd env so the postprovision hook (deploy_data_agents.py)
// can wire the Foundry agents to the right Fabric workspace + semantic model.
output FABRIC_WORKSPACE_ID string = fabricWorkspaceId
output PAYER_SEMANTIC_MODEL string = semanticModel
