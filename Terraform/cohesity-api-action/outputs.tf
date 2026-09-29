# cohesity_api.sh always prints {"result": "<json-encoded response string>"}
# (that shape is required by the external data source contract it was
# originally written for) -- so decoding needs two passes here too, same
# as cohesity-api-module/outputs.tf.

output "raw_response" {
  description = "Raw JSON string returned by the Cohesity API call."
  value       = jsondecode(data.local_file.action_response.content).result
}

output "response" {
  description = "Parsed JSON response as a Terraform object -- index into this for specific fields."
  value       = jsondecode(jsondecode(data.local_file.action_response.content).result)
}
