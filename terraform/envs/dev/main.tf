module "network" {
  source               = "../../modules/network"
  vcn_cidr             = "10.0.0.0/16"
  compartment_id       = var.compartment_id
  bastion_allowed_cidr = var.bastion_allowed_cidr
}

# Servers: one bastion plus var.fleet_size private fleet servers.
module "fleet" {
  source            = "../../modules/fleet"
  compartment_id    = var.compartment_id
  public_subnet_id  = module.network.public_subnet_id
  private_subnet_id = module.network.private_subnet_id
  bastion_nsg_id    = module.network.bastion_nsg_id
  fleet_nsg_id      = module.network.fleet_nsg_id
  lb_nsg_id         = module.network.lb_nsg_id
  tenancy_id        = var.tenancy_ocid
  alarm_email       = var.alarm_email
  ssh_public_key    = file(pathexpand("~/.ssh/gateway_lab.pub"))
  fleet_size        = var.fleet_size
  fleet_shape       = var.fleet_shape
  bastion_shape     = var.bastion_shape
  app_dir           = "${path.root}/../../../app/deploy"
}
