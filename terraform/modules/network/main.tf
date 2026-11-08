resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_id
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "gateway-lab-vcn"
  dns_label      = "gatewaylab"
}