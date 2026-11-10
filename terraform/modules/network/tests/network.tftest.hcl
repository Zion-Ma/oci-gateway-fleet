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
#   [ ] nsg_rules_follow_least_privilege  - NSGs + their security rules
#   [ ] bastion_cidr_rejects_open_world   - var.bastion_allowed_cidr validation
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
  compartment_id      = "ocid1.compartment.oc1..test"
  vcn_cidr            = "10.0.0.0/16"
  public_subnet_cidr  = "10.0.1.0/24"
  private_subnet_cidr = "10.0.2.0/24"
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
  assert {
    condition     = oci_core_subnet.public.route_table_id == oci_core_route_table.public.id
    error_message = "Public subnet must use the public route table"
  }
}

# Behavior: private route table has no Internet Gateway rule (it should only
# route out via NAT Gateway / Service Gateway).
run "private_route_table_has_no_igw" {
  command = apply

  assert {
    condition = length([
      for r in oci_core_route_table.private.route_rules :
      r if r.destination == "0.0.0.0/0" && r.network_entity_id == oci_core_nat_gateway.main.id
    ]) == 1
    error_message = "Private route table must send 0.0.0.0/0 to the NAT Gateway"
  }

  assert {
    condition = length([
      for r in oci_core_route_table.private.route_rules :
      r if r.destination_type == "SERVICE_CIDR_BLOCK" && r.network_entity_id == oci_core_service_gateway.main.id
    ]) == 1
    error_message = "Private route table must send Oracle services traffic to the Service Gateway"
  }

  assert {
    condition     = oci_core_subnet.private.route_table_id == oci_core_route_table.private.id
    error_message = "Private subnet must use the private route table"
  }
}

# Behavior: NSG rules follow least privilege (only the LB is internet-facing,
# fleet only reachable from LB/bastion NSGs, bastion only from the admin IP).
# Needs command = apply: the fleet NSG's SSH rule sources from the bastion
# NSG's `id`, which (like above) is only known after apply.
run "nsg_rules_follow_least_privilege" {
  command = apply

  # 1. Exactly one ingress rule accepts traffic from the internet.
  assert {
    condition = length([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules : k
      if r.direction == "INGRESS" && r.source == "0.0.0.0/0"
    ]) == 1
    error_message = "Exactly one ingress rule may be open to 0.0.0.0/0"
  }

  # 2. That rule belongs to the load balancer and is port 80 only.
  assert {
    condition = alltrue([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules :
      r.network_security_group_id == oci_core_network_security_group.lb.id
      && r.tcp_options[0].destination_port_range[0].min == 80
      && r.tcp_options[0].destination_port_range[0].max == 80
      if r.direction == "INGRESS" && r.source == "0.0.0.0/0"
    ])
    error_message = "The only internet-facing rule must be the load balancer NSG on TCP 80"
  }

  # 3. Fleet app port (8000) is reachable only from the LB NSG.
  assert {
    condition = length([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules : k
      if r.network_security_group_id == oci_core_network_security_group.fleet.id
      && r.direction == "INGRESS"
      && r.tcp_options[0].destination_port_range[0].min == 8000
      ]) > 0 && alltrue([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules :
      r.source == oci_core_network_security_group.lb.id
      if r.network_security_group_id == oci_core_network_security_group.fleet.id
      && r.direction == "INGRESS"
      && r.tcp_options[0].destination_port_range[0].min == 8000
    ])
    error_message = "Fleet port 8000 must be reachable only from the LB NSG"
  }

  # 4. Fleet SSH (22) is reachable only from the bastion NSG.
  assert {
    condition = length([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules : k
      if r.network_security_group_id == oci_core_network_security_group.fleet.id
      && r.direction == "INGRESS"
      && r.tcp_options[0].destination_port_range[0].min == 22
      ]) > 0 && alltrue([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules :
      r.source == oci_core_network_security_group.bastion.id
      if r.network_security_group_id == oci_core_network_security_group.fleet.id
      && r.direction == "INGRESS"
      && r.tcp_options[0].destination_port_range[0].min == 22
    ])
    error_message = "Fleet SSH must be reachable only from the bastion NSG"
  }

  # 5. Fleet ingress is limited to those two (port, source) pairs.
  assert {
    condition = alltrue([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules :
      contains([22, 8000], r.tcp_options[0].destination_port_range[0].min)
      if r.network_security_group_id == oci_core_network_security_group.fleet.id
      && r.direction == "INGRESS"
    ])
    error_message = "Fleet may accept ingress only on ports 22 and 8000"
  }

  # 6. Bastion accepts traffic only from the admin IP.
  assert {
    condition = length([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules : k
      if r.network_security_group_id == oci_core_network_security_group.bastion.id
      && r.direction == "INGRESS"
      ]) > 0 && alltrue([
      for k, r in oci_core_network_security_group_security_rule.nsg_rules :
      r.source == var.bastion_allowed_cidr
      if r.network_security_group_id == oci_core_network_security_group.bastion.id
      && r.direction == "INGRESS"
    ])
    error_message = "Bastion may accept traffic only from bastion_allowed_cidr"
  }
}

# Behavior: an open-to-the-world (or non-/32) bastion CIDR is rejected by
# variable validation, so the real config can't drift from what the test
# above exercises with its placeholder IP.
run "bastion_cidr_rejects_open_world" {
  command = plan

  variables {
    bastion_allowed_cidr = "0.0.0.0/0"
  }

  expect_failures = [var.bastion_allowed_cidr]
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
  assert {
    condition     = length(oci_core_default_security_list.default.egress_security_rules) == 0
    error_message = "Default security list must have no egress rules (use NSGs instead)"
  }
}