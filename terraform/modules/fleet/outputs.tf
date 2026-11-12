output "bastion_public_ip" {
  value = oci_core_instance.bastion.public_ip
}

output "fleet_private_ips" {
  value = oci_core_instance.fleet[*].private_ip
}

output "fleet_instance_ids" {
  value = oci_core_instance.fleet[*].id
}

output "lb_public_ip" {
  value = oci_load_balancer_load_balancer.main.ip_address_details[0].ip_address
}
