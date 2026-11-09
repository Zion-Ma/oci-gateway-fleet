# ---------------------------------------------------------------------------
# PROGRESS CHECKLIST — each run block below is RED until main.tf declares the
# resource it references. Run `terraform test` after each change to main.tf
# and watch blocks flip from fail to pass one at a time:
#
#   [ ] vcn_uses_cidr_variable            - oci_core_vcn.main
#   [ ] subnets_have_correct_cidrs        - oci_core_subnet.public / .private
#   [ ] private_subnet_blocks_public_ip   - oci_core_subnet.private
#   [ ] gateways_exist                    - internet/nat/service gateways
#   [ ] public_route_table_routes_via_igw - oci_core_route_table.public
#   [ ] private_route_table_has_no_igw    - oci_core_route_table.private
#   [ ] nsgs_exist_without_open_ssh       - NSGs + their security rules
#   [ ] default_security_list_has_no_ssh  - oci_core_default_security_list.default
#
# This file assumes variables.tf will define: compartment_id, vcn_cidr,
# public_subnet_cidr, private_subnet_cidr, bastion_allowed_cidr.
#
# It also assumes main.tf will name resources exactly as referenced in the
# `condition` expressions below (e.g. oci_core_subnet.public, a single
# oci_core_network_security_group_security_rule resource using for_each so
# all rules can be scanned in one expression). Rename the resources in
# main.tf to match, or rename the references here — just keep them in sync.
# ---------------------------------------------------------------------------

# mock_data fills in the one data source main.tf reads (the "all services"
# lookup the Service Gateway needs). Without this, mock_provider would mock
# it as an empty services list and `services[0]` would error.
mock_provider "oci" {
  mock_data "oci_core_services" {
    defaults = {
      services = [{
        id          = "ocid1.service.oc1..test"
        name        = "All IAD Services In Oracle Services Network"
        cidr_block  = "all-iad-services-in-oracle-services-network"
        description = "test"
      }]
    }
  }
}

variables {
  compartment_id       = "ocid1.compartment.oc1..test"
  vcn_cidr             = "10.0.0.0/16"
  public_subnet_cidr   = "10.0.1.0/24"
  private_subnet_cidr  = "10.0.2.0/24"
  # TEST-NET-3 placeholder, not a real home IP.
  bastion_allowed_cidr = "203.0.113.4/32"
}

run "vcn_uses_cidr_variable" {
  command = plan

  assert {
    condition     = oci_core_vcn.main.cidr_blocks[0] == "10.0.0.0/16"
    error_message = "VCN must use the CIDR from var.vcn_cidr"
  }
}

# Behavior: public and private subnets exist with the right CIDRs.
# Plan-level check: cidr_block is set directly from our variables, so it's
# known at plan time (no need to wait for apply).
run "subnets_have_correct_cidrs" {
  command = plan

  assert {
    condition     = oci_core_subnet.public.cidr_block == var.public_subnet_cidr
    error_message = "Public subnet must use var.public_subnet_cidr"
  }

  assert {
    condition     = oci_core_subnet.private.cidr_block == var.private_subnet_cidr
    error_message = "Private subnet must use var.private_subnet_cidr"
  }
}

# Behavior: private subnet has prohibit_public_ip_on_vnic = true, so fleet
# servers never get a public IP even by accident.
run "private_subnet_blocks_public_ip" {
  command = plan

  assert {
    condition     = oci_core_subnet.private.prohibit_public_ip_on_vnic == true
    error_message = "Private subnet must set prohibit_public_ip_on_vnic = true"
  }
}

# Behavior: Internet, NAT, and Service Gateways exist. Reference resolution
# itself proves existence (plan errors with "reference to undeclared
# resource" otherwise, as seen before main.tf existed); the asserts add a
# couple of literal, plan-known sanity checks on top.
run "gateways_exist" {
  command = plan

  assert {
    condition     = oci_core_internet_gateway.main.compartment_id == var.compartment_id
    error_message = "Internet Gateway must exist in the target compartment"
  }

  assert {
    condition     = oci_core_nat_gateway.main.compartment_id == var.compartment_id
    error_message = "NAT Gateway must exist in the target compartment"
  }

  assert {
    condition     = oci_core_nat_gateway.main.block_traffic == false
    error_message = "NAT Gateway must not be blocking traffic"
  }

  assert {
    condition     = oci_core_service_gateway.main.compartment_id == var.compartment_id
    error_message = "Service Gateway must exist in the target compartment"
  }
}

# Behavior: public route table sends 0.0.0.0/0 to the Internet Gateway.
# Needs command = apply: network_entity_id references the gateway's `id`,
# which is provider-computed and only resolved (even to a mock value) after
# apply, not at plan.
run "public_route_table_routes_via_igw" {
  command = apply

  assert {
    condition = length([
      for r in oci_core_route_table.public.route_rules :
      r if r.destination == "0.0.0.0/0" && r.network_entity_id == oci_core_internet_gateway.main.id
    ]) == 1
    error_message = "Public route table must send 0.0.0.0/0 to the Internet Gateway"
  }
}

# Behavior: private route table has no Internet Gateway rule (it should only
# route out via NAT Gateway / Service Gateway).
run "private_route_table_has_no_igw" {
  command = apply

  assert {
    condition = length([
      for r in oci_core_route_table.private.route_rules :
      r if r.network_entity_id == oci_core_internet_gateway.main.id
    ]) == 0
    error_message = "Private route table must not route through the Internet Gateway"
  }
}

# Behavior: NSGs exist, and no rule allows TCP 22 from 0.0.0.0/0.
# Needs command = apply: the fleet NSG's SSH rule sources from the bastion
# NSG's `id`, which (like above) is only known after apply.
run "nsgs_exist_without_open_ssh" {
  command = apply

  assert {
    condition     = oci_core_network_security_group.lb.compartment_id == var.compartment_id
    error_message = "Load balancer NSG must exist"
  }

  assert {
    condition     = oci_core_network_security_group.bastion.compartment_id == var.compartment_id
    error_message = "Bastion NSG must exist"
  }

  assert {
    condition     = oci_core_network_security_group.fleet.compartment_id == var.compartment_id
    error_message = "Fleet NSG must exist"
  }

  assert {
    condition = length([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules : k
      if r.direction == "INGRESS"
      && r.source == "0.0.0.0/0"
      && r.protocol == "6"
      && try(r.tcp_options[0].destination_port_range[0].min, null) == 22
      && try(r.tcp_options[0].destination_port_range[0].max, null) == 22
    ]) == 0
    error_message = "No NSG rule may allow TCP 22 from 0.0.0.0/0"
  }
}

# Behavior: the default security list (auto-created with every VCN, and
# notoriously left with an open SSH rule by default) has no open SSH rule.
# We expect main.tf to manage it explicitly via oci_core_default_security_list
# and strip its rules down so NSGs are the only source of truth.
run "default_security_list_has_no_ssh" {
  command = apply

  assert {
    condition     = length(oci_core_default_security_list.default.ingress_security_rules) == 0
    error_message = "Default security list must have no ingress rules (use NSGs instead)"
  }
}