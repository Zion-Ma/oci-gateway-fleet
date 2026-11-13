mock_provider "oci" {
  mock_data "oci_identity_availability_domains" {
    defaults = { availability_domains = [{ name = "TEST:US-ASHBURN-AD-1" }] }
  }
  mock_data "oci_objectstorage_namespace" {
    defaults = { namespace = "testns" }
  }
  mock_data "oci_identity_domains" {
    defaults = { domains = [{ url = "https://idcs-test.identity.oraclecloud.com:443" }] }
  }
  mock_resource "oci_load_balancer_load_balancer" {
    defaults = { ip_address_details = [{ ip_address = "203.0.113.10" }] }
  }
  mock_data "oci_core_images" {
    defaults = { images = [{ id = "ocid1.image.oc1..test" }] }
  }
}

variables {
  compartment_id      = "ocid1.compartment.oc1..test"
  public_subnet_id    = "ocid1.subnet.oc1..public"
  private_subnet_id   = "ocid1.subnet.oc1..private"
  bastion_nsg_id      = "ocid1.nsg.oc1..bastion"
  fleet_nsg_id        = "ocid1.nsg.oc1..fleet"
  lb_nsg_id           = "ocid1.nsg.oc1..lb"
  tenancy_id          = "ocid1.tenancy.oc1..test"
  alarm_email         = "alerts@example.com"
  ssh_public_key      = "ssh-ed25519 AAAATEST test"
  fleet_size          = 3
  fleet_shape         = "VM.Standard.E5.Flex"
  bastion_shape       = "VM.Standard.E2.1.Micro"
  app_dir             = "../../../app/deploy"
  vcn_id              = "ocid1.vcn.oc1..test"
  private_subnet_cidr = "10.0.2.0/24"
}

# Behavior: fleet servers are private. The count follows var.fleet_size, and
# every server sits in the private subnet, has no public IP and uses the Fleet
# NSG. With count, oci_core_instance.fleet is a list, so each check loops over
# all servers; one bad server fails the whole assert.
# Plan-level check: all of these values are set directly in main.tf.
run "fleet_servers_are_private" {
  command = plan

  # The number of servers must come from the variable (the test sets 3, not
  # the default 2, so a hard-coded count would fail here).
  assert {
    condition     = length(oci_core_instance.fleet) == var.fleet_size
    error_message = "Fleet must create exactly var.fleet_size servers"
  }

  # Every server's network card is in the private subnet.
  assert {
    condition = alltrue([
      for i in oci_core_instance.fleet :
      i.create_vnic_details[0].subnet_id == var.private_subnet_id
    ])
    error_message = "Every fleet server must be in var.private_subnet_id"
  }

  # No server gets a public IP. tostring() because the provider stores this
  # flag as a string.
  assert {
    condition = alltrue([
      for i in oci_core_instance.fleet :
      tostring(i.create_vnic_details[0].assign_public_ip) == "false"
    ])
    error_message = "Fleet servers must not be assigned a public IP"
  }

  # Every server is in the Fleet NSG (nsg_ids is a set, so convert to a list
  # for contains()).
  assert {
    condition = alltrue([
      for i in oci_core_instance.fleet :
      contains(tolist(i.create_vnic_details[0].nsg_ids), var.fleet_nsg_id)
    ])
    error_message = "Every fleet server must have var.fleet_nsg_id in its NSG list"
  }
}

# Behavior: the bastion and fleet servers use separate shapes, so the bastion
# can stay on the free E2.1.Micro while the fleet uses a paid Flex shape.
run "shapes_are_separate" {
  command = plan

  # Every fleet server uses var.fleet_shape.
  assert {
    condition = alltrue([
      for i in oci_core_instance.fleet :
      i.shape == var.fleet_shape
    ])
    error_message = "Every fleet server must use var.fleet_shape"
  }

  # The bastion uses var.bastion_shape.
  assert {
    condition     = oci_core_instance.bastion.shape == var.bastion_shape
    error_message = "The bastion must use var.bastion_shape"
  }
}

# Behavior: the bastion is the one public server. It has no count, so it is a
# single instance, not a list.
run "bastion_is_public" {
  command = plan

  # The bastion's network card is in the public subnet.
  assert {
    condition     = oci_core_instance.bastion.create_vnic_details[0].subnet_id == var.public_subnet_id
    error_message = "The bastion must be in var.public_subnet_id"
  }

  # The bastion gets a public IP so you can SSH to it.
  assert {
    condition     = tostring(oci_core_instance.bastion.create_vnic_details[0].assign_public_ip) == "true"
    error_message = "The bastion must be assigned a public IP"
  }

  # The bastion is in the Bastion NSG, which only allows your admin IP.
  assert {
    condition     = contains(tolist(oci_core_instance.bastion.create_vnic_details[0].nsg_ids), var.bastion_nsg_id)
    error_message = "The bastion must have var.bastion_nsg_id in its NSG list"
  }
}

# Behavior: a public load balancer fronts the fleet. Users hit the listener on
# port 80, the backend set picks a server round robin, and each server is
# health-checked on port 8000 at /health.
run "load_balancer_fronts_the_fleet" {
  command = plan

  # The LB is public, in the public subnet, and in the LB NSG.
  assert {
    condition     = oci_load_balancer_load_balancer.main.is_private == false
    error_message = "The load balancer must be public"
  }

  assert {
    condition     = contains(tolist(oci_load_balancer_load_balancer.main.subnet_ids), var.public_subnet_id)
    error_message = "The load balancer must be in var.public_subnet_id"
  }

  assert {
    condition     = contains(tolist(oci_load_balancer_load_balancer.main.network_security_group_ids), var.lb_nsg_id)
    error_message = "The load balancer must have var.lb_nsg_id in its NSG list"
  }

  # Health check: HTTP, port 8000, path /health.
  assert {
    condition = (
      oci_load_balancer_backend_set.fleet.health_checker[0].protocol == "HTTP" &&
      oci_load_balancer_backend_set.fleet.health_checker[0].port == 8000 &&
      oci_load_balancer_backend_set.fleet.health_checker[0].url_path == "/health"
    )
    error_message = "Health check must be HTTP on port 8000 at /health"
  }

  # Traffic is spread round robin.
  assert {
    condition     = oci_load_balancer_backend_set.fleet.policy == "ROUND_ROBIN"
    error_message = "The backend set must use ROUND_ROBIN"
  }

  # One backend per fleet server, each on port 8000.
  assert {
    condition     = length(oci_load_balancer_backend.fleet) == var.fleet_size
    error_message = "There must be one backend per fleet server"
  }

  assert {
    condition     = alltrue([for b in oci_load_balancer_backend.fleet : b.port == 8000])
    error_message = "Every backend must use port 8000"
  }

  # Listener: HTTP on port 80.
  assert {
    condition     = oci_load_balancer_listener.http.protocol == "HTTP" && oci_load_balancer_listener.http.port == 80
    error_message = "The listener must be HTTP on port 80"
  }
}

# Behavior: notes live in a private bucket that only fleet servers can write to.
run "notes_bucket_is_private" {
  command = plan

  # No public access of any kind.
  assert {
    condition     = oci_objectstorage_bucket.notes.access_type == "NoPublicAccess"
    error_message = "The notes bucket must be NoPublicAccess"
  }

  # The bucket name comes from the variable, so the policy and the app agree.
  assert {
    condition     = oci_objectstorage_bucket.notes.name == var.notes_bucket_name
    error_message = "The bucket must be named var.notes_bucket_name"
  }
}

# Behavior: least privilege. Only fleet servers carry the role=fleet tag, the
# dynamic group matches on that tag, and the policy is scoped to one bucket.
run "only_fleet_can_write_notes" {
  command = plan

  # Every fleet server carries gateway-lab.role = fleet.
  assert {
    condition = alltrue([
      for i in oci_core_instance.fleet :
      i.defined_tags["gateway-lab.role"] == "fleet"
    ])
    error_message = "Every fleet server must be tagged gateway-lab.role=fleet"
  }

  # The dynamic group matches on the tag, not on the compartment or OCIDs.
  assert {
    condition     = strcontains(oci_identity_domains_dynamic_resource_group.fleet.matching_rule, "tag.gateway-lab.role.value='fleet'")
    error_message = "The matching rule must match the gateway-lab.role=fleet tag"
  }

  assert {
    condition     = !strcontains(oci_identity_domains_dynamic_resource_group.fleet.matching_rule, "instance.compartment.id") && !strcontains(oci_identity_domains_dynamic_resource_group.fleet.matching_rule, "instance.id")
    error_message = "The matching rule must not match on compartment or instance OCIDs"
  }

  # One statement: the dynamic group (with domain prefix) manages objects in
  # this compartment, only in the notes bucket.
  assert {
    condition     = length(oci_identity_policy.notes_writer.statements) == 1
    error_message = "The policy must have exactly one statement"
  }

  assert {
    condition = (
      strcontains(oci_identity_policy.notes_writer.statements[0], "manage objects") &&
      strcontains(oci_identity_policy.notes_writer.statements[0], "'Default'/'gateway-lab-fleet'") &&
      strcontains(oci_identity_policy.notes_writer.statements[0], "target.bucket.name='${var.notes_bucket_name}'") &&
      strcontains(oci_identity_policy.notes_writer.statements[0], "compartment id ${var.compartment_id}")
    )
    error_message = "The policy must be scoped to the dynamic group, this compartment and the notes bucket"
  }
}

# Behavior: the app learns its bucket name through the systemd unit.
run "app_gets_bucket_name" {
  command = plan

  assert {
    condition     = strcontains(base64decode(oci_core_instance.fleet[0].metadata["user_data"]), "Environment=NOTES_BUCKET=${var.notes_bucket_name}")
    error_message = "cloud-init must set NOTES_BUCKET in the systemd unit"
  }
}

# Behavior: the bastion never joins the dynamic group. Its defined_tags are only
# known after apply, so this run uses the mock provider's apply (creates nothing real).
run "bastion_has_no_role_tag" {
  command = apply

  assert {
    condition     = !contains(keys(coalesce(oci_core_instance.bastion.defined_tags, {})), "gateway-lab.role")
    error_message = "The bastion must not carry the gateway-lab.role tag"
  }

  # Sanity check that the apply-mode run still sees the fleet tag.
  assert {
    condition     = alltrue([for i in oci_core_instance.fleet : i.defined_tags["gateway-lab.role"] == "fleet"])
    error_message = "Fleet servers must carry the gateway-lab.role tag"
  }
}

# Behavior: an email arrives when any backend is unhealthy for 1 minute. A topic
# holds the email subscription, and an alarm on the load balancer's unhealthy
# backend count publishes to that topic. Ids are known only after apply, so this
# run uses the mock provider's apply (creates nothing real).
run "unhealthy_backend_sends_email" {
  command = apply

  # The topic lives in the project compartment.
  assert {
    condition     = oci_ons_notification_topic.alerts.compartment_id == var.compartment_id
    error_message = "The topic must be in var.compartment_id"
  }

  # The subscription sends email to the address from the variable, on that topic.
  assert {
    condition     = oci_ons_subscription.email.protocol == "EMAIL" && oci_ons_subscription.email.endpoint == var.alarm_email
    error_message = "The subscription must be EMAIL to var.alarm_email"
  }

  assert {
    condition     = oci_ons_subscription.email.topic_id == oci_ons_notification_topic.alerts.id
    error_message = "The subscription must be on the alerts topic"
  }

  # The alarm watches the load balancer service's metrics, for this load balancer.
  assert {
    condition     = oci_monitoring_alarm.unhealthy_backend.namespace == "oci_lbaas"
    error_message = "The alarm must use the oci_lbaas namespace"
  }

  assert {
    condition     = strcontains(oci_monitoring_alarm.unhealthy_backend.query, "unhealthyBackendServers") && strcontains(oci_monitoring_alarm.unhealthy_backend.query, oci_load_balancer_load_balancer.main.id)
    error_message = "The alarm query must use unhealthyBackendServers for this load balancer"
  }

  # Fires on any unhealthy backend (more than zero), once it lasts 1 minute.
  assert {
    condition     = strcontains(oci_monitoring_alarm.unhealthy_backend.query, ".max() > 0")
    error_message = "The alarm must fire when the unhealthy count is above zero"
  }

  assert {
    condition     = oci_monitoring_alarm.unhealthy_backend.pending_duration == "PT1M"
    error_message = "The alarm must wait 1 minute (PT1M) before firing"
  }

  # It publishes to the alerts topic, and it is switched on.
  assert {
    condition     = contains(tolist(oci_monitoring_alarm.unhealthy_backend.destinations), oci_ons_notification_topic.alerts.id)
    error_message = "The alarm must publish to the alerts topic"
  }

  assert {
    condition     = oci_monitoring_alarm.unhealthy_backend.is_enabled == true
    error_message = "The alarm must be enabled"
  }
}

# Behavior: Object Storage accepts note writes only through the VCN's Service
# Gateway. A network source names the VCN and the private subnet range. The
# policy requires that source by name, next to the bucket name, so a request
# that falls back to NAT and the public internet is refused.
run "notes_only_via_service_gateway" {
  command = plan

  # The network source lives in the tenancy root and has the expected name.
  assert {
    condition     = oci_identity_network_source.fleet_vcn.compartment_id == var.tenancy_id
    error_message = "The network source must be created in the tenancy root"
  }

  assert {
    condition     = oci_identity_network_source.fleet_vcn.name == "gateway-lab-fleet-vcn"
    error_message = "The network source must be named gateway-lab-fleet-vcn"
  }

  # Exactly one virtual source: this VCN, and only the private subnet range.
  assert {
    condition     = length(tolist(oci_identity_network_source.fleet_vcn.virtual_source_list)) == 1
    error_message = "The network source must have exactly one virtual source"
  }

  assert {
    condition     = tolist(oci_identity_network_source.fleet_vcn.virtual_source_list)[0].vcn_id == var.vcn_id
    error_message = "The virtual source must be var.vcn_id"
  }

  assert {
    condition     = toset(tolist(oci_identity_network_source.fleet_vcn.virtual_source_list)[0].ip_ranges) == toset([var.private_subnet_cidr])
    error_message = "The virtual source must list only the private subnet range"
  }

  assert {
    condition     = !contains(tolist(tolist(oci_identity_network_source.fleet_vcn.virtual_source_list)[0].ip_ranges), "0.0.0.0/0")
    error_message = "The virtual source must not allow 0.0.0.0/0"
  }

  # No public IP source: the only way in is through the VCN.
  assert {
    condition     = length(try(tolist(oci_identity_network_source.fleet_vcn.public_source_list), [])) == 0
    error_message = "The network source must have no public source list"
  }

  # The statement has BOTH conditions inside one all { ... } block.
  assert {
    condition     = length(regexall("all \\{[^}]*target\\.bucket\\.name='${var.notes_bucket_name}'[^}]*\\}", oci_identity_policy.notes_writer.statements[0])) == 1
    error_message = "The policy must require the bucket name inside all { ... }"
  }

  assert {
    condition     = length(regexall("all \\{[^}]*request\\.networkSource\\.name='gateway-lab-fleet-vcn'[^}]*\\}", oci_identity_policy.notes_writer.statements[0])) == 1
    error_message = "The policy must require the network source name inside all { ... }"
  }

  # The old safeguard must not come back: request.vcn.id is deprecated here.
  assert {
    condition     = !strcontains(oci_identity_policy.notes_writer.statements[0], "request.vcn.id")
    error_message = "The policy must not use request.vcn.id"
  }
}
