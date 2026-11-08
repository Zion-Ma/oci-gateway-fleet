variable "compartment_id" {
  type        = string
  description = "OCID of the compartment for all network resources"
}

variable "vcn_cidr" {
  type        = string
  description = "IP range for the VCN"
  default     = "10.0.0.0/16"
}