variable "region" {
  type        = string
  description = "OCI region to deploy into"
  default     = "us-ashburn-1"
}

variable "compartment_id" {
  type        = string
  description = "OCID of the gateway-lab compartment"
}

variable "vcn_cidr" {
  type        = string
  description = "IP range for the VCN"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  type        = string
  description = "IP range for the public subnet (load balancer, bastion)"
  default     = "10.0.1.0/24"
}

variable "private_subnet_cidr" {
  type        = string
  description = "IP range for the private subnet (fleet servers)"
  default     = "10.0.2.0/24"
}

variable "bastion_allowed_cidr" {
  type        = string
  description = "108.236.198.55/32, the only source allowed to SSH to the bastion"
  # No default on purpose: each environment must set its own admin IP,
  # so nobody gets SSH access by accident.

  validation {
    condition     = can(cidrhost(var.bastion_allowed_cidr, 0)) && can(regex("/32$", var.bastion_allowed_cidr))
    error_message = "bastion_allowed_cidr must be a single IPv4 address in /32 form (e.g. 203.0.113.4/32)."
  }
}

# Number of fleet servers; 0 until you are ready to pay for instances.
variable "fleet_size" {
  type        = number
  description = "Number of fleet servers"
  default     = 0
}

# Fleet servers use a paid flexible shape (covered by trial credits).
variable "fleet_shape" {
  type        = string
  description = "Compute shape for the fleet servers"
  default     = "VM.Standard.E5.Flex"
}

# The bastion stays on the Always Free micro shape.
variable "bastion_shape" {
  type        = string
  description = "Compute shape for the bastion"
  default     = "VM.Standard.E2.1.Micro"
}

# Tenancy OCID, used to find the identity domain for the dynamic group.
variable "tenancy_ocid" {
  type        = string
  description = "OCID of the tenancy"
}
