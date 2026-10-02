from fastapi import FastAPI, HTTPException
import subprocess
import requests
import json
import base64

app = FastAPI(title="Proxmox Native Web Orchestrator API")

ETCD_HOST = "http://10.10.10.58:2379"

@app.get("/")
def root():
    return {"status": "Orchestrator Running", "system": "Proxmox Cluster Manager"}

@app.get("/api/cluster/status")
def get_cluster_status():
    """Mengambil status kluster Proxmox via CLI pvecm."""
    try:
        output = subprocess.check_output(["pvecm", "status"]).decode()
        return {"status": "success", "raw_output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vm/migrate")
def migrate_vm(vmid: int, target_node: str):
    """Memicu VM Migration otomatis sesuai flowchart."""
    try:
        cmd = f"qm migrate {vmid} {target_node} --online"
        subprocess.Popen(cmd, shell=True)
        return {"status": "migration_started", "vmid": vmid, "target": target_node}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)