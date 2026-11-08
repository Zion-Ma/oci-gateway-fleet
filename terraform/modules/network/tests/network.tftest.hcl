mock_provider "oci" {}

variables {
  compartment_id = "ocid1.compartment.oc1..test"
  vcn_cidr       = "10.0.0.0/16"
}

run "vcn_uses_cidr_variable" {
  command = plan

  assert {
    condition     = oci_core_vcn.main.cidr_blocks[0] == "10.0.0.0/16"
    error_message = "VCN must use the CIDR from var.vcn_cidr"
  }
}