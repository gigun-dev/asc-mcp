terraform {
  required_version = ">= 1.10.0"
  required_providers {
    cloudflare = { source = "cloudflare/cloudflare", version = "= 5.24.0" }
  }
}
provider "cloudflare" {}
variable "account_id" { type = string }
variable "mcp_hostname" { type = string }
variable "install_hostname" { type = string }
variable "allowed_emails" { type = set(string) }
variable "oauth_redirect_uris" { type = list(string) }
variable "resource_prefix" {
  type    = string
  default = "asc-mcp"
}
resource "cloudflare_d1_database" "jobs" {
  account_id = var.account_id
  name       = "${var.resource_prefix}-jobs"
  read_replication = { mode = "disabled" }
}
variable "manage_distribution" {
  type    = bool
  default = true
}
resource "cloudflare_r2_bucket" "artifacts" {
  count      = var.manage_distribution ? 1 : 0
  account_id = var.account_id
  name       = "${var.resource_prefix}-artifacts"
}
resource "cloudflare_zero_trust_access_application" "mcp" {
  account_id   = var.account_id
  name         = "${var.resource_prefix} MCP"
  type         = "mcp"
  destinations = [{ type = "public", uri = var.mcp_hostname }]
  oauth_configuration = {
    enabled = true
    dynamic_client_registration = {
      enabled                = true
      allow_any_on_localhost = true
      allow_any_on_loopback  = true
      allowed_uris           = var.oauth_redirect_uris
    }
    grant = { access_token_lifetime = "15m", session_duration = "168h" }
  }
  policies = [{ name = "Build owners", decision = "allow", precedence = 1, include = [for email in var.allowed_emails : { email = { email = email } }] }]
}
resource "cloudflare_zero_trust_access_application" "install" {
  count                = var.manage_distribution ? 1 : 0
  account_id           = var.account_id
  name                 = "${var.resource_prefix} installs"
  type                 = "self_hosted"
  destinations         = [{ type = "public", uri = var.install_hostname }]
  app_launcher_visible = true
  policies             = [{ name = "Install owners", decision = "allow", precedence = 1, include = [for email in var.allowed_emails : { email = { email = email } }] }]
}
resource "cloudflare_zero_trust_access_application" "download" {
  count                = var.manage_distribution ? 1 : 0
  account_id           = var.account_id
  name                 = "${var.resource_prefix} signed downloads"
  type                 = "self_hosted"
  destinations         = [{ type = "public", uri = "${var.install_hostname}/download/*" }]
  app_launcher_visible = false
  # Deploy Worker signature verification before enabling this path exception.
  policies = [{ name = "Worker signed URL authorization", decision = "bypass", precedence = 1, include = [{ everyone = {} }] }]
}
output "database_id" { value = cloudflare_d1_database.jobs.id }
output "mcp_audience" { value = cloudflare_zero_trust_access_application.mcp.aud }
output "install_audience" { value = try(cloudflare_zero_trust_access_application.install[0].aud, null) }
output "artifact_bucket" { value = try(cloudflare_r2_bucket.artifacts[0].name, null) }

variable "state_passphrase" {
  type      = string
  sensitive = true
}
terraform {
  encryption {
    key_provider "pbkdf2" "state" {
      passphrase = var.state_passphrase
    }
    method "aes_gcm" "state" {
      keys = key_provider.pbkdf2.state
    }
    state {
      method   = method.aes_gcm.state
      enforced = true
    }
    plan {
      method   = method.aes_gcm.state
      enforced = true
    }
  }
}
