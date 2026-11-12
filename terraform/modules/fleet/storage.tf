# Object Storage and least-privilege IAM for /notes.
# Only fleet servers (tagged gateway-lab.role=fleet) may write; the bastion may not.

# The account-wide storage namespace the bucket lives in.
data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.compartment_id
}

# Private bucket for notes: no public access of any kind.
resource "oci_objectstorage_bucket" "notes" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = var.notes_bucket_name
  access_type    = "NoPublicAccess"
}

# Tag namespace + tag that mark a server's role. The dynamic group matches on it.
resource "oci_identity_tag_namespace" "gateway_lab" {
  compartment_id = var.compartment_id
  name           = "gateway-lab"
  description    = "Tags for the gateway lab"
}

resource "oci_identity_tag" "role" {
  tag_namespace_id = oci_identity_tag_namespace.gateway_lab.id
  name             = "role"
  description      = "What a server is for (fleet servers get role=fleet)"
}

# The identity domain that holds the dynamic group (this tenancy uses domains,
# so the classic oci_identity_dynamic_group does not apply).
data "oci_identity_domains" "this" {
  compartment_id = var.tenancy_id
  display_name   = var.identity_domain_name
}

# Dynamic group: every instance carrying the role=fleet tag, nothing else.
resource "oci_identity_domains_dynamic_resource_group" "fleet" {
  idcs_endpoint = data.oci_identity_domains.this.domains[0].url
  display_name  = "gateway-lab-fleet"
  description   = "Fleet servers (tagged role=fleet)"
  # OCI adds the OCITags extension schema itself; listing it avoids a permanent diff.
  schemas = [
    "urn:ietf:params:scim:schemas:oracle:idcs:DynamicResourceGroup",
    "urn:ietf:params:scim:schemas:oracle:idcs:extension:OCITags",
  ]
  matching_rule = "tag.${oci_identity_tag_namespace.gateway_lab.name}.${oci_identity_tag.role.name}.value='fleet'"
}

# Policy: fleet servers manage objects in this one bucket. It is attached to the
# gateway-lab compartment itself, which is enough because it only grants access
# inside that compartment (no root-compartment policy needed).
resource "oci_identity_policy" "notes_writer" {
  compartment_id = var.compartment_id
  name           = "gateway-lab-notes-writer"
  description    = "Fleet servers may write notes to the notes bucket only"
  statements = [
    "Allow dynamic-group '${var.identity_domain_name}'/'${oci_identity_domains_dynamic_resource_group.fleet.display_name}' to manage objects in compartment id ${var.compartment_id} where target.bucket.name='${oci_objectstorage_bucket.notes.name}'"
  ]
}
