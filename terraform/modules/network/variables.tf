variable "region" {
  type    = string
  default = "us-ashburn-1"
}

variable "compartment_id" {
  type        = string
  description = "OCID of the compartment for all network resources"
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
  description = "CIDR allowed to SSH into the bastion (your home IP, as a /32)"
  # No default on purpose: this must be set explicitly per the
  # default_security_list_has_no_ssh / nsg_rules_follow_least_privilege tests.

  validation {
    condition     = can(cidrhost(var.bastion_allowed_cidr, 0)) && can(regex("/32$", var.bastion_allowed_cidr))
    error_message = "bastion_allowed_cidr must be a single IPv4 address in /32 form (e.g. 203.0.113.4/32)."
  }
}