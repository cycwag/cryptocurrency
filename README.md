# Crypto Observability Stack on AWS EKS

Project pembelajaran end-to-end implementasi **Observability Stack (Prometheus, Grafana Cloud, Alertmanager)** di atas **Amazon EKS (Kubernetes)** untuk memonitor aplikasi crypto price tracker kustom dengan budget ketat.

---

## 1. Tujuan & Constraint Project

- **Tujuan**: Mempelajari deployment dan pengelolaan observability stack tingkat industri (Prometheus Operator, Grafana, Alertmanager) pada cluster Kubernetes (EKS), memonitor metrik custom dari aplikasi microservice buatan sendiri, dan memicu alerting otomatis saat terjadi simulasi kegagalan (*failure simulation*).
- **Budget**: Total Rp 200.000 (~$12 USD).
- **Pola Pemakaian**: ~1 jam/sesi belajar. Infrastruktur di-destroy setiap kali sesi selesai agar tidak ada tagihan saat tidak digunakan.
- **Biaya per Sesi**:
  - EKS Control Plane: ~$0.10/jam
  - 1x EC2 `t3.small` Spot Instance: ~$0.016/jam
  - AWS NAT Gateway: ~$0.045/jam
  - **Total**: ~**$0.16/jam (± Rp 2.500/jam)**. Budget Rp 200rb mencukupi hingga ~80 sesi belajar.
- **Keputusan Arsitektur Kunci**:
  - **AWS EKS** (bukan Minikube/k3s lokal) untuk mendapatkan *real-world cloud experience*.
  - **Spot Instance** untuk worker node guna menghemat biaya komputasi hingga 70-90%.
  - **Remote Write ke Grafana Cloud** (Free Tier): Data histori dan dashboard tersimpan permanen di cloud tanpa perlu persistent volume EBS berbayar di AWS, sehingga data tidak hilang saat cluster EKS di-destroy.

---

## 2. Arsitektur Sistem

```text
[Internet / CoinGecko API]
           ▲
           │ (Fetch harga tiap 30s)
[AWS VPC: Private Subnet]
  └─ EKS Worker Node (t3.small Spot)
       ├─ Pod: currency-tracker (Python Flask + Gunicorn)
       │    ├─ Expose /metrics (Prometheus Client)
       │    ├─ Expose /health (Liveness & Readiness Probes)
       │    └─ Endpoint /fail & /toggle-fail (Failure Simulation)
       │
       ├─ Kubernetes Service (ClusterIP:80 -> Pod:5000)
       ├─ ServiceMonitor (Scrape /metrics tiap 15s)
       │
       └─ Prometheus Agent (kube-prometheus-stack)
            │
            ▼ (Remote Write TLS)
[Grafana Cloud (External)]
  ├─ Hosted Prometheus TSDB (14 days retention)
  ├─ 6 Panel Observability Dashboard
  └─ Alerting Rule -> Email Notification ([FIRING] & [RESOLVED])
```

---

## 3. Struktur Repository

```text
currency/
├── terraform/                  # Infrastruktur AWS (IaC)
│   ├── provider.tf             # AWS Provider (~> 5.0)
│   ├── backend.tf              # Local state
│   ├── variables.tf            # Region (us-east-1), cluster name, instance type, allowed_ip
│   ├── vpc.tf                  # VPC, 2 Public & 2 Private Subnets, IGW, NAT Gateway, Route Tables
│   ├── eks.tf                  # EKS v1.34 Control Plane & Managed Node Group (SPOT t3.small)
│   └── outputs.tf              # Cluster endpoint & credentials output
│
├── k8s/                        # Manifest Kubernetes & Monitoring
│   ├── app-deployment.yaml     # Deployment (non-root UID 1000, read-only rootfs + emptyDir /tmp, probes) & Service
│   ├── servicemonitor.yaml     # Custom Resource Definition (CRD) Prometheus Operator untuk scrape /metrics
│   ├── monitoring-secret.yaml  # Kredensial Grafana Cloud (Instance ID & API Token) - Masuk .gitignore
│   └── monitoring-values.yaml  # Helm values: disable Grafana lokal, limit resource, remote_write config
│
├── app/                        # Aplikasi Crypto Price Tracker
│   ├── main.py                 # Backend Flask + prometheus_client + CoinGecko fetch loop
│   ├── requirements.txt        # Flask, requests, prometheus_client, gunicorn
│   ├── Dockerfile              # Python 3.12-slim, non-root appuser, Gunicorn single-worker
│   ├── templates/
│   │   ├── index.html          # Watchlist table 6 koin (Stockbit Dark Terminal UI)
│   │   └── coin.html           # Detail halaman koin + Chart.js histori harga 24h
│   └── static/
│       └── style.css           # Styling terminal dark (green-up, red-down, Inter typography)
│
├── scripts/                    # Skrip Automasi Sesi Belajar
│   ├── start.ps1               # Terraform apply -> Update kubeconfig -> Helm install -> Deploy app
│   └── stop.ps1                # Cleanup K8s resources -> Terraform destroy
│
├── .gitignore                  # Melindungi state file Terraform dan API token rahasia
└── README.md                   # Dokumentasi lengkap project
```

---

## 4. Custom Metrics & Observability Dashboard

Aplikasi mengekspos metrik Prometheus standar industri di endpoint `/metrics`:
- `crypto_price_usd{symbol="BTC|ETH|SOL|DOGE|XRP|LINK"}` (Gauge): Harga terkini koin crypto.
- `price_fetch_total{status="success|error"}` (Counter): Jumlah percobaan fetch ke CoinGecko upstream.
- `price_fetch_latency_seconds` (Gauge): Durasi respons request ke API upstream.

### Dashboard 6 Panel di Grafana Cloud:
1. **Bitcoin Price / Crypto Prices** (Time Series): Grafik pergerakan harga real-time.
2. **Network Throughput** (Time Series): Trafik masuk (*Inbound Rx*) dan keluar (*Outbound Tx*) container dalam `Bytes/sec`.
3. **Network Packet Drops** (Stat): Indikator lampu hijau (`0 drop`) atau merah jika terjadi degradasi jaringan.
4. **API Fetch Rate (Req/s)** (Time Series): Laju request `success` (hijau) vs `error` (merah).
5. **Upstream Latency** (Gauge Speedometer): Waktu respons API upstream (<1s Hijau, 1-3s Kuning, >3s Merah).
6. **Pod CPU & Memory Usage** (Time Series / Gauge): Utilisasi sumber daya pod terhadap batas limit (CPU 250m, RAM 500MiB) untuk mencegah crash *OOMKilled*.

---

## 5. Cara Menjalankan

### Prasyarat
- AWS CLI terkonfigurasi dengan akses Administrator (`aws configure`).
- Terraform (>= 1.5.0), Kubectl, Helm, dan Docker Desktop terinstall di laptop.
- Akun gratis di [Grafana Cloud](https://grafana.com) untuk mendapatkan:
  - Remote Write Endpoint URL
  - Prometheus Instance ID (`username`)
  - Access Policy Token (`password`)

### Memulai Sesi Belajar
1. Isi kredensial Grafana Cloud pada `k8s/monitoring-secret.yaml` dan `k8s/monitoring-values.yaml`.
2. Jalankan skrip startup otomatis dari root project:
   ```powershell
   .\scripts\start.ps1
   ```
   *(Proses memakan waktu ~12–15 menit untuk provisioning infrastruktur AWS dan mendeploy monitoring stack).*
3. Untuk mengakses tampilan web aplikasi di laptop:
   ```powershell
   kubectl port-forward svc/currency-tracker 5000:80
   ```
   Buka browser di `http://localhost:5000`.
4. Buka Grafana Cloud untuk melihat dashboard dan grafik real-time.

### Menguji Failure & Alerting
1. Di web aplikasi (`http://localhost:5000`), klik tombol **`Fail ON`**.
2. Di Grafana Cloud, amati panel **API Fetch Rate**: garis `success` turun ke 0 dan garis `error` melonjak naik.
3. Alert rule `CryptoFetchFailed` akan berubah status dari `Normal` -> `Pending` -> `Firing`.
4. Notifikasi email alarm otomatis masuk ke inbox Gmail Anda.
5. Klik **`Fail OFF`** untuk memulihkan aplikasi kembali normal.

### Mengakhiri Sesi Belajar (Wajib Menghindari Tagihan AWS)
Begitu sesi belajar selesai, selalu jalankan skrip cleanup untuk menghapus seluruh resource cloud:
```powershell
.\scripts\stop.ps1
```
*(Menghapus resource K8s, memutus ELB/ENI, lalu menjalankan `terraform destroy` hingga VPC dan NAT Gateway terhapus bersih).*
Semua dashboard dan data histori tetap tersimpan permanen di Grafana Cloud.
