$ErrorActionPreference = 'Stop'

Write-Host "=== [1/3] Cleaning up App & Monitoring Resources ===" -ForegroundColor Yellow
& kubectl delete -f k8s/ --recursive --ignore-not-found
& helm uninstall monitoring --ignore-not-found

Write-Host "=== [2/3] Waiting for AWS to reconcile (Detach ELB/EBS) ===" -ForegroundColor Gray
Start-Sleep -Seconds 30

Write-Host "=== [3/3] Destroying Terraform Infrastructure ===" -ForegroundColor Red
Set-Location -LiteralPath "terraform"
terraform destroy -auto-approve
Set-Location -LiteralPath ".."

Write-Host "=== Infrastructure Destroyed! ===" -ForegroundColor Green
