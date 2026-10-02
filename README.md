# proxmox-orchestrator

![Proxmox VE](https://img.shields.io/badge/Proxmox--VE-9.x-orange?style=for-the-badge&logo=proxmox)
![Tailscale Network](https://img.shields.io/badge/Network-Tailscale--Mesh-blue?style=for-the-badge&logo=tailscale)
![etcd State Store](https://img.shields.io/badge/State--Store-etcd-green?style=for-the-badge&logo=etcd)
![Python Backend](https://img.shields.io/badge/Backend-FastAPI%20%2F%20Python-005577?style=for-the-badge&logo=python)

**Automated Orchestration Engine & State Synchronization Daemon** untuk kluster Proxmox VE (*nested virtualization*). Sistem ini mengimplementasikan pendekatan **Desired State Configuration (DSC)** berbasis `etcd` sebagai *Single Source of Truth* (SSOT) untuk mendeteksi *configuration drift*, melakukan *auto-healing/reconciliation* otomatis, dan memfasilitasi *control plane* via Web Native API.

---

## 📐 Arsitektur Sistem & Workflow

Sistem bekerja dengan membandingkan keadaan riil (*Actual State*) setiap node Proxmox terhadap keadaan yang diinginkan (*Desired State*) yang tersimpan di `etcd`:

```mermaid
graph TD
    Admin["Administrator / Web Native Dashboard"] --> ControlPlane["FastAPI Control Plane"]
    ControlPlane --> ETCD["etcd SSOT Database<br/>(Desired State Reference)"]
    
    ETCD --> Node1["pve1-a1<br/>(Agent)"]
    ETCD --> Node2["pve-a2<br/>(Agent)"]
    ETCD --> Node3["pve-a3 / pve-a4<br/>(Agent)"]
    
    Node1 --> DriftTest["Compare State & Drift Test"]
    Node2 --> DriftTest
    Node3 --> DriftTest
    
    DriftTest --> Discrepancy{"Discrepancy?"}
    
    Discrepancy -- YES --> AutoReconcile["Auto-Reconcile"]
    AutoReconcile --> ValidateMTU["Validate MTU/Net"]
    
    Discrepancy -- NO --> ConfigConsistent["Config Consistent"]
    ConfigConsistent --> MigrationReady["VM Live Migration Ready"]
```
