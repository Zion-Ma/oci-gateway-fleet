terraform {
  required_version = ">= 1.6"
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

provider "oci" {
  config_file_profile = "DEFAULT"
}
