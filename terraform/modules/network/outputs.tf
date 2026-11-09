output "vcn_id" {
  value = oci_core_vcn.main.id
}

output "public_subnet_id" {
  value = oci_core_subnet.public.id
}

output "private_subnet_id" {
  value = oci_core_subnet.private.id
}

output "lb_nsg_id" {
  value = oci_core_network_security_group.lb.id
}

output "bastion_nsg_id" {
  value = oci_core_network_security_group.bastion.id
}

output "fleet_nsg_id" {
  value = oci_core_network_security_group.fleet.id
}
