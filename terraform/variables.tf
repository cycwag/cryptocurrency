variable "region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS Cluster Name"
  type        = string
  default     = "currency-cluster"
}

variable "node_instance_type" {
  description = "Worker Node Instance Type"
  type        = string
  default     = "t3.small"
}

variable "allowed_ip" {
  description = "Public IP for EKS API access"
  type        = string
  default     = "0.0.0.0/0"
}
