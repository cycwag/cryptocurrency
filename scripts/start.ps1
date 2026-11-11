$ErrorActionPreference = 'Stop'

Write-Host "=== [1/4] Applying Terraform Infrastructure ===" -ForegroundColor Cyan
Set-Location -LiteralPath "terraform"
terraform init
terraform apply -auto-approve
Set-Location -LiteralPath ".."

Write-Host "=== [2/4] Updating Kubeconfig ===" -ForegroundColor Cyan
& aws eks update-kubeconfig --region us-east-1 --name currency-cluster

Write-Host "=== [3/4] Deploying Secrets & Monitoring Stack ===" -ForegroundColor Cyan
& kubectl apply -f k8s/monitoring-secret.yaml
& helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
& helm repo update
& helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -f k8s/monitoring-values.yaml

Write-Host "=== [4/4] Deploying Crypto Tracker App ===" -ForegroundColor Cyan
& kubectl apply -f k8s/app-deployment.yaml
& kubectl apply -f k8s/servicemonitor.yaml

Write-Host "=== Deployment Finished Successfully ===" -ForegroundColor Green
