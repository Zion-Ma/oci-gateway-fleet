resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_id
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "gateway-lab-vcn"
  dns_label      = "gatewaylab"
}

# test: gateways_exist
resource "oci_core_internet_gateway" "main" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "internet-gateway"
  enabled        = true
}

resource "oci_core_nat_gateway" "main" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "nat-gateway"
  block_traffic  = false
}

# "All ... Services In Oracle Services Network" lets the service gateway
# reach Object Storage without a route through the NAT Gateway.
data "oci_core_services" "all_oci_services" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

resource "oci_core_service_gateway" "main" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "service-gateway"

  services {
    service_id = data.oci_core_services.all_oci_services.services[0].id
  }
}

# test: public_route_table_routes_via_igw
resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "public-route-table"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }
}

# test: private_route_table_has_no_igw
resource "oci_core_route_table" "private" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "private-route-table"

  route_rules {
    destination       = data.oci_core_services.all_oci_services.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.main.id
  }

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.main.id
  }
}

# test: subnets_have_correct_cidrs, private_subnet_blocks_public_ip
resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = var.public_subnet_cidr
  route_table_id             = oci_core_route_table.public.id
  display_name               = "public-subnet"
  dns_label                  = "public"
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_subnet" "private" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = var.private_subnet_cidr
  route_table_id             = oci_core_route_table.private.id
  display_name               = "private-subnet"
  dns_label                  = "private"
  prohibit_public_ip_on_vnic = true
}

# test: nsg_rules_follow_least_privilege
resource "oci_core_network_security_group" "lb" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "lb-nsg"
}

resource "oci_core_network_security_group" "bastion" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "bastion-nsg"
}

resource "oci_core_network_security_group" "fleet" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.main.id
  display_name   = "fleet-nsg"
}

# One map entry per row of the security rules table in the project plan.
# Kept as a single for_each resource (rather than one resource block per
# rule) so the "no rule allows TCP 22 from 0.0.0.0/0" test can scan every
# rule in one for-expression instead of needing updates every time a rule
# is added.
locals {
  nsg_rules = {
    lb_ingress_http = {
      nsg_id           = oci_core_network_security_group.lb.id
      direction        = "INGRESS"
      port             = 80
      source           = "0.0.0.0/0"
      source_type      = "CIDR_BLOCK"
      destination      = null
      destination_type = null
    }
    lb_egress_app = {
      nsg_id           = oci_core_network_security_group.lb.id
      direction        = "EGRESS"
      port             = 8000
      source           = null
      source_type      = null
      destination      = oci_core_network_security_group.fleet.id
      destination_type = "NETWORK_SECURITY_GROUP"
    }
    bastion_ingress_ssh = {
      nsg_id           = oci_core_network_security_group.bastion.id
      direction        = "INGRESS"
      port             = 22
      source           = var.bastion_allowed_cidr
      source_type      = "CIDR_BLOCK"
      destination      = null
      destination_type = null
    }
    bastion_egress_ssh = {
      nsg_id           = oci_core_network_security_group.bastion.id
      direction        = "EGRESS"
      port             = 22
      source           = null
      source_type      = null
      destination      = oci_core_network_security_group.fleet.id
      destination_type = "NETWORK_SECURITY_GROUP"
    }
    fleet_ingress_app = {
      nsg_id           = oci_core_network_security_group.fleet.id
      direction        = "INGRESS"
      port             = 8000
      source           = oci_core_network_security_group.lb.id
      source_type      = "NETWORK_SECURITY_GROUP"
      destination      = null
      destination_type = null
    }
    fleet_ingress_ssh = {
      nsg_id           = oci_core_network_security_group.fleet.id
      direction        = "INGRESS"
      port             = 22
      source           = oci_core_network_security_group.bastion.id
      source_type      = "NETWORK_SECURITY_GROUP"
      destination      = null
      destination_type = null
    }
    fleet_egress_https = {
      nsg_id           = oci_core_network_security_group.fleet.id
      direction        = "EGRESS"
      port             = 443
      source           = null
      source_type      = null
      destination      = "0.0.0.0/0"
      destination_type = "CIDR_BLOCK"
    }
    fleet_egress_http = {
      nsg_id           = oci_core_network_security_group.fleet.id
      direction        = "EGRESS"
      port             = 80
      source           = null
      source_type      = null
      destination      = "0.0.0.0/0"
      destination_type = "CIDR_BLOCK"
    }
  }
}

resource "oci_core_network_security_group_security_rule" "nsg_rules" {
  for_each  = local.nsg_rules
  stateless = false

  network_security_group_id = each.value.nsg_id
  direction                 = each.value.direction
  protocol                  = "6" # TCP

  source           = each.value.source
  source_type      = each.value.source_type
  destination      = each.value.destination
  destination_type = each.value.destination_type

  tcp_options {
    destination_port_range {
      min = each.value.port
      max = each.value.port
    }
  }
}

# test: default_security_list_has_no_ssh
# OCI auto-creates a default security list with every VCN (including an
# open SSH rule). NSGs above are the real source of truth, so this strips
# the default list down to nothing rather than leaving it as a backdoor.
resource "oci_core_default_security_list" "default" {
  manage_default_resource_id = oci_core_vcn.main.default_security_list_id
  compartment_id             = var.compartment_id
  display_name               = "default-security-list-disabled"
}