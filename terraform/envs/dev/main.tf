module "network" {
  source = "../../modules/network"
  vcn_cidr             = "10.0.0.0/16"
  compartment_id       = var.compartment_id
  bastion_allowed_cidr = var.bastion_allowed_cidr
}
