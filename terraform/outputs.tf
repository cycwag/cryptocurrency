output "cluster_endpoint" {
  description = "Endpoint API Server EKS"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_name" {
  description = "Nama EKS Cluster"
  value       = aws_eks_cluster.main.name
}

output "region" {
  description = "AWS Region"
  value       = var.region
}
