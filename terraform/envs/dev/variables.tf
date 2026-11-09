variable "compartment_id" {
  type        = string
  description = "OCID of the gateway-lab compartment"
}

variable "bastion_allowed_cidr" {
  type        = string
  description = "Your home IP as a /32"
}
