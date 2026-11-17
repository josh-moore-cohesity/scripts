output "raw_response" {
  description = "Raw JSON string returned by the Cohesity API call."
  value       = data.external.cohesity_api_call.result.result
}

output "response" {
  description = "Parsed JSON response as a Terraform object -- index into this for specific fields, e.g. module.cohesity_cluster.response.name"
  value       = jsondecode(data.external.cohesity_api_call.result.result)
}
