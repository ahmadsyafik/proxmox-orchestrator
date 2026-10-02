import json
import requests

ETCD_HOST = "http://10.10.10.58:2379"

# Desired Configuration Reference (SSOT)
desired_state = {
    "cluster_name": "cluster-pa",
    "expected_nodes": ["pve1-a1", "pve-a2", "pve-a3", "pve-a4"],
    "network_config": {
        "bridge": "vmbr0",
        "mtu": 1500,
        "vlan_aware": "yes"
    },
    "reconciliation_policy": {
        "auto_heal": True,
        "check_interval_seconds": 10
    }
}

def set_desired_state():
    # etcd v3 REST API Key Value Store
    key = "cluster/desired_state"
    url = f"{ETCD_HOST}/v3/kv/put"
    
    import base64
    key_b64 = base64.b64encode(key.encode()).decode()
    val_b64 = base64.b64encode(json.dumps(desired_state).encode()).decode()
    
    payload = {"key": key_b64, "value": val_b64}
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("[SUCCESS] Desired State berhasil disimpan ke etcd SSOT!")
    else:
        print(f"[ERROR] Gagal menyimpan state: {response.text}")

if __name__ == "__main__":
    set_desired_state()