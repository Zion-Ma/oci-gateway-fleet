module "network" {
  source = "../../modules/network"

  compartment_id       = var.compartment_id
  bastion_allowed_cidr = var.bastion_allowed_cidr
}

output "vcn_id" {
  value = module.network.vcn_id
}

output "public_subnet_id" {
  value = module.network.public_subnet_id
}

output "private_subnet_id" {
  value = module.network.private_subnet_id
}
