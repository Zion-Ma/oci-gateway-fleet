# OCID of the compartment that holds every fleet resource (from dev).
variable "compartment_id" {
  type        = string
  description = "OCID of the compartment for all fleet resources"
}

# Subnet for the bastion (from the network module's output).
variable "public_subnet_id" {
  type        = string
  description = "OCID of the public subnet (bastion, load balancer)"
}

# Subnet for the fleet servers (from the network module's output).
variable "private_subnet_id" {
  type        = string
  description = "OCID of the private subnet (fleet servers)"
}

# Firewall group for the bastion (from the network module's output).
variable "bastion_nsg_id" {
  type        = string
  description = "OCID of the Bastion NSG, which only allows SSH from the admin IP"
}

# Firewall group for the fleet servers (from the network module's output).
variable "fleet_nsg_id" {
  type        = string
  description = "OCID of the Fleet NSG, which only allows the load balancer and bastion"
}

# Public key installed for the opc user (read from ~/.ssh/gateway_lab.pub).
variable "ssh_public_key" {
  type        = string
  description = "SSH public key for the opc user on the bastion and fleet servers"
}

# How many fleet servers to create; drives `count` in main.tf.
variable "fleet_size" {
  type        = number
  description = "Number of fleet servers"
  default     = 2
}

# Shape for the fleet servers (also used to pick a compatible image).
variable "fleet_shape" {
  type        = string
  description = "Compute shape for the fleet servers"
  default     = "VM.Standard.E5.Flex"
}

# Shape for the bastion; stays on the Always Free micro shape.
variable "bastion_shape" {
  type        = string
  description = "Compute shape for the bastion"
  default     = "VM.Standard.E2.1.Micro"
}

variable "app_dir" {
  type        = string
  description = "Path to the app's deploy/ folder"
}

variable "app_version" {
  type    = string
  default = "v1"
}

variable "ocpus" {
  type    = number
  default = 1
}

variable "memory_in_gbs" {
  type    = number
  default = 4
}
# Firewall group for the load balancer (from the network module's output).
variable "lb_nsg_id" {
  type        = string
  description = "OCID of the LB NSG"
}

# Tenancy OCID: identity domains and their dynamic groups live at tenancy level.
variable "tenancy_id" {
  type        = string
  description = "OCID of the tenancy (used to look up the identity domain)"
}

# Identity domain that owns the dynamic group; also the policy name prefix.
variable "identity_domain_name" {
  type        = string
  description = "Identity domain for the dynamic group"
  default     = "Default"
}

# Bucket for notes; the app gets this name as NOTES_BUCKET.
variable "notes_bucket_name" {
  type        = string
  description = "Name of the private Object Storage bucket for notes"
  default     = "gateway-lab-notes"
}
