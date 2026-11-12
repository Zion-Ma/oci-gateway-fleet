data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_id
}

data "oci_core_images" "ol9" {
  compartment_id           = var.compartment_id
  operating_system         = "Oracle Linux"
  operating_system_version = "9"
  shape                    = var.fleet_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "fleet" {
  count               = var.fleet_size
  compartment_id      = var.compartment_id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  shape               = var.fleet_shape
  display_name        = "fleet-${count.index + 1}"
  # The role tag puts this server in the dynamic group (the bastion has none).
  defined_tags = {
    "${oci_identity_tag_namespace.gateway_lab.name}.${oci_identity_tag.role.name}" = "fleet"
  }
  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ol9.images[0].id
  }

  create_vnic_details {
    subnet_id        = var.private_subnet_id
    assign_public_ip = false
    nsg_ids          = [var.fleet_nsg_id]
    hostname_label   = "fleet${count.index + 1}"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/templates/cloud-init.yaml.tftpl", {
      server_js_b64    = filebase64("${var.app_dir}/server.js")
      package_json_b64 = filebase64("${var.app_dir}/package.json")
      app_version      = var.app_version
      notes_bucket     = var.notes_bucket_name
    }))
  }
  dynamic "shape_config" {
    for_each = endswith(var.fleet_shape, ".Flex") ? [1] : []
    content {
      ocpus         = var.ocpus
      memory_in_gbs = var.memory_in_gbs
    }
  }
}

resource "oci_core_instance" "bastion" {
  compartment_id      = var.compartment_id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  shape               = var.bastion_shape
  display_name        = "bastion"

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ol9.images[0].id
  }

  create_vnic_details {
    subnet_id        = var.public_subnet_id
    assign_public_ip = true
    nsg_ids          = [var.bastion_nsg_id]
    hostname_label   = "bastion"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
  }
  dynamic "shape_config" {
    for_each = endswith(var.bastion_shape, ".Flex") ? [1] : []
    content {
      ocpus         = var.ocpus
      memory_in_gbs = var.memory_in_gbs
    }
  }
}


# Public load balancer in the public subnet; 10 Mbps flexible is the free size.
resource "oci_load_balancer_load_balancer" "main" {
  compartment_id             = var.compartment_id
  display_name               = "fleet-lb"
  shape                      = "flexible"
  subnet_ids                 = [var.public_subnet_id]
  is_private                 = false
  network_security_group_ids = [var.lb_nsg_id]

  shape_details {
    minimum_bandwidth_in_mbps = 10
    maximum_bandwidth_in_mbps = 10
  }
}

# The group of fleet servers: round robin, health-checked on /health.
resource "oci_load_balancer_backend_set" "fleet" {
  load_balancer_id = oci_load_balancer_load_balancer.main.id
  name             = "fleet"
  policy           = "ROUND_ROBIN"

  health_checker {
    protocol          = "HTTP"
    port              = 8000
    url_path          = "/health"
    return_code       = 200
    interval_ms       = 10000
    timeout_in_millis = 3000
    retries           = 3
  }
}

# One backend per fleet server; the IP follows the instance if it is replaced.
resource "oci_load_balancer_backend" "fleet" {
  count            = var.fleet_size
  load_balancer_id = oci_load_balancer_load_balancer.main.id
  backendset_name  = oci_load_balancer_backend_set.fleet.name
  ip_address       = oci_core_instance.fleet[count.index].private_ip
  port             = 8000
}

# What users hit: HTTP on port 80, sent to the fleet backend set.
resource "oci_load_balancer_listener" "http" {
  load_balancer_id         = oci_load_balancer_load_balancer.main.id
  name                     = "http"
  default_backend_set_name = oci_load_balancer_backend_set.fleet.name
  port                     = 80
  protocol                 = "HTTP"
}
