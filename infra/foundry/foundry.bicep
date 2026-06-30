// =============================================================================
// foundry.bicep — Resource-group-scoped Azure AI Foundry resources.
//
// Deployed by main.bicep into rg-<environmentName>. See main.bicep header for
// the rationale (Basic agent setup; no capability host / ACR / BYO data).
// =============================================================================

@description('Location for all resources.')
param location string

@description('Deterministic token for globally-unique resource names.')
param resourceToken string

@description('Tags applied to every resource.')
param tags object

@description('Principal ID granted Azure AI User + Cognitive Services User on the account. Empty = skip the role assignments (e.g. when the caller lacks Microsoft.Authorization/roleAssignments/write).')
param deployingPrincipalId string

@allowed([
  'User'
  'ServicePrincipal'
])
@description('Principal type of deployingPrincipalId.')
param deployingPrincipalType string

@description('Model to deploy.')
param modelName string

@description('Model version.')
param modelVersion string

@description('Model deployment SKU.')
param modelSkuName string

@description('Model deployment capacity (thousands of TPM).')
param modelCapacity int

// Account name must be globally unique, 2-64 chars, alphanumeric + hyphens.
var accountName = 'aif-payer-${resourceToken}'
var projectName = 'proj-payer-${resourceToken}'
var modelDeploymentName = modelName

// Built-in role definition IDs (tenant-wide, stable GUIDs).
var azureAiUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User

// ---- Foundry account -------------------------------------------------------
// kind=AIServices + allowProjectManagement=true makes this a Foundry-capable
// account that can host projects and serve the Responses/Agents API.
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Custom subdomain is REQUIRED for token-based (AAD) auth, which the
    // hosted-agent client uses via DefaultAzureCredential.
    customSubDomainName: accountName
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// ---- Foundry project -------------------------------------------------------
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Payer Demo'
    description: 'Foundry project hosting the Payer demo orchestrator + hosted agents.'
  }
}

// ---- Model deployment ------------------------------------------------------
// Deployed on the ACCOUNT (model deployments are account-scoped and shared by
// all projects on the account).
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

// ---- RBAC: let the deploying principal create/manage agents ----------------
// create_or_update_agent against the Responses API requires data-plane access
// to the account. Azure AI User covers agent/thread operations; Cognitive
// Services User covers model inference. Scope = account (inherited by project).
resource azureAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployingPrincipalId)) {
  name: guid(account.id, deployingPrincipalId, azureAiUserRoleId)
  scope: account
  properties: {
    principalId: deployingPrincipalId
    principalType: deployingPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAiUserRoleId)
  }
}

resource cognitiveServicesUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployingPrincipalId)) {
  name: guid(account.id, deployingPrincipalId, cognitiveServicesUserRoleId)
  scope: account
  properties: {
    principalId: deployingPrincipalId
    principalType: deployingPrincipalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
  }
}

// ---- Outputs ---------------------------------------------------------------
output accountName string = account.name
output projectName string = project.name
// Account AAD endpoint (e.g. https://aif-payer-xxxx.cognitiveservices.azure.com/).
output accountEndpoint string = account.properties.endpoint
// Project endpoint the hosted-agent SDK (AzureAIAgentClient) expects. The
// canonical Foundry project endpoint is built from the account's custom
// subdomain on the services.ai.azure.com host:
//   https://<account>.services.ai.azure.com/api/projects/<project>
// We construct it from the custom subdomain (== account name) rather than the
// account.properties.endpoints dictionary, whose keys are not guaranteed to be
// populated at deploy time.
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${project.name}'
output modelDeploymentName string = modelDeployment.name
