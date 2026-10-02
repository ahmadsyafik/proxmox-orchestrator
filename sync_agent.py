import time
import json
import subprocess
import requests
import base64

ETCD_HOST = "http://10.10.10.58:2379"
NODE_NAME = subprocess.check_output(["hostname"]).decode().strip()

def get_desired_state():
    url = f"{ETCD_HOST}/v3/kv/range"
    key_b64 = base64.b64encode(b"cluster/desired_state").decode()
    response = requests.post(url, json={"key": key_b64})
    
    if response.status_code == 200:
        kvs = response.json().get("kvs", [])
        if kvs:
            val_str = base64.b64decode(kvs[0]["value"]).decode()
            return json.loads(val_str)
    return None

def get_actual_network_state(bridge_name):
    """Memeriksa kondisi fisik/network aktual di node."""
    try:
        cmd = f"ip -j link show {bridge_name}"
        output = subprocess.check_output(cmd, shell=True).decode()
        data = json.loads(output)
        return {
            "bridge": bridge_name,
            "mtu": data[0].get("mtu"),
            "state": data[0].get("operstate")
        }
    except Exception as e:
        return {"error": str(e)}

def reconcile_network(desired_net):
    """Melakukan perbaikan otomatis (Reconciliation) jika ditemukan Discrepancy."""
    bridge = desired_net["bridge"]
    target_mtu = desired_net["mtu"]
    
    print(f"[RECONCILIATION] Mengubah MTU {bridge} menjadi {target_mtu}...")
    cmd = f"ip link set dev {bridge} mtu {target_mtu}"
    subprocess.run(cmd, shell=True, check=True)
    print(f"[RECONCILIATION SUCCESS] Konfigurasi {bridge} telah disesuaikan!")

def main_loop():
    print(f"[*] Sync Agent pve Daemon Aktif di Node: {NODE_NAME}")
    while True:
        desired = get_desired_state()
        if desired:
            target_net = desired["network_config"]
            actual_net = get_actual_network_state(target_net["bridge"])
            
            print(f"\n--- Checking State on {NODE_NAME} ---")
            print(f"Actual State  : {actual_net}")
            print(f"Desired State : {target_net}")
            
            # Deteksi Perbedaan Configuration (Discrepancy Detected?)
            if "mtu" in actual_net and actual_net["mtu"] != target_net["mtu"]:
                print("[!] DISCREPANCY DETECTED! Menjalankan Rekonsiliasi...")
                reconcile_network(target_net)
            else:
                print("[OK] Configuration Consistent.")
        
        time.sleep(10)

if __name__ == "__main__":
    main_loop()