output "vcn_id" {
  value = module.network.vcn_id
}

output "public_subnet_id" {
  value = module.network.public_subnet_id
}

output "private_subnet_id" {
  value = module.network.private_subnet_id
}

# IP to SSH to (the only way into the fleet).
output "bastion_public_ip" {
  description = "Public IP of the bastion"
  value       = module.fleet.bastion_public_ip
}

# Private IPs of the fleet servers (the tests check they are unreachable).
output "fleet_private_ips" {
  description = "Private IPs of the fleet servers"
  value       = module.fleet.fleet_private_ips
}

# Exact instance OCIDs, so tests do not depend on server names.
output "fleet_instance_ids" {
  description = "OCIDs of the fleet servers"
  value       = module.fleet.fleet_instance_ids
}

# Public IP of the load balancer: where users reach the app.
output "lb_public_ip" {
  description = "Public IP of the load balancer"
  value       = module.fleet.lb_public_ip
}

# OCID of the load balancer, used by tools/lb_client.py.
output "lb_id" {
  description = "OCID of the load balancer"
  value       = module.fleet.lb_id
}
