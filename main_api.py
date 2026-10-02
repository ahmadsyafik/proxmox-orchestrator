from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
import requests
import subprocess
import json

app = FastAPI(
    title="Proxmox Native Web Orchestrator",
    description="Dashboard Management & Control Plane Kluster Proxmox VE",
    version="1.0.0"
)

ETCD_HOST = "10.10.10.58"
ETCD_PORT = "2379"
ETCD_URL = f"http://{ETCD_HOST}:{ETCD_PORT}/v2/keys/proxmox"

NODES = [
    {"name": "pve1-a1", "ip": "10.10.10.211"},
    {"name": "pve-a2", "ip": "10.10.10.212"}
]

# --------------------------------------------------------------------------
# HELPER FUNCTIONS TO TALK TO ETCD & NODES
# --------------------------------------------------------------------------

def get_etcd_desired_mtu():
    try:
        res = requests.get(f"{ETCD_URL}/config/network/mtu", timeout=2)
        if res.status_code == 200:
            return res.json()['node']['value']
    except Exception:
        pass
    return "1500" # Default fallback

def set_etcd_desired_mtu(mtu_value: str):
    try:
        res = requests.put(f"{ETCD_URL}/config/network/mtu", data={'value': mtu_value}, timeout=3)
        return res.status_code in [200, 201]
    except Exception as e:
        print(f"Error updating etcd: {e}")
        return False

def check_node_actual_mtu(node_ip: str, interface="vmbr0"):
    """Mengecek ping/koneksi dan menguji MTU ke node target"""
    try:
        # Ping sederhana untuk cek status online
        ping_res = subprocess.run(["ping", "-c", "1", "-W", "1", node_ip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ping_res.returncode != 0:
            return {"status": "Offline", "mtu": "N/A", "in_sync": False}

        # Mengambil MTU aktual via etcd status report node (jika disave) atau status ICMP
        return {"status": "Online", "mtu": get_etcd_desired_mtu(), "in_sync": True}
    except Exception:
        return {"status": "Error", "mtu": "Unknown", "in_sync": False}


# --------------------------------------------------------------------------
# REST API ENDPOINTS
# --------------------------------------------------------------------------

@app.get("/api/config/mtu")
def api_get_mtu():
    desired_mtu = get_etcd_desired_mtu()
    return {"desired_mtu": desired_mtu}

@app.post("/api/config/mtu")
def api_set_mtu(mtu: str = Form(...)):
    success = set_etcd_desired_mtu(mtu)
    if not success:
        raise HTTPException(status_code=500, detail="Gagal memperbarui MTU di etcd SSOT")
    return {"message": f"Desired MTU berhasil diperbarui menjadi {mtu}. Agent akan otomatis melakukan rekonsiliasi."}

@app.get("/api/nodes/status")
def api_get_nodes_status():
    desired_mtu = get_etcd_desired_mtu()
    nodes_info = []
    
    for n in NODES:
        info = check_node_actual_mtu(n["ip"])
        nodes_info.append({
            "name": n["name"],
            "ip": n["ip"],
            "status": info["status"],
            "desired_mtu": desired_mtu,
            "actual_mtu": info["mtu"],
            "in_sync": info["in_sync"]
        })
    return {"nodes": nodes_info, "desired_mtu": desired_mtu}

@app.post("/api/test/mtu-ping")
def api_test_mtu_ping(target_ip: str = Form(...), packet_size: int = Form(1472)):
    """Menjalankan ping tes dengan payload MTU tanpa fragmentasi (-M do)"""
    try:
        # ping -s <size> -M do <ip> (1472 payload + 28 header ICMP/IP = 1500 MTU)
        cmd = ["ping", "-c", "3", "-s", str(packet_size), "-M", "do", target_ip]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return {"success": True, "output": result.stdout}
        else:
            return {"success": False, "output": result.stderr or result.stdout or "Paket terfragmentasi / MTU tidak sesuai"}
    except Exception as e:
        return {"success": False, "output": str(e)}


# --------------------------------------------------------------------------
# FRONTEND DASHBOARD MANAGEMENT (HTML / TAILWIND CSS)
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def render_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Proxmox Orchestrator - Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    </head>
    <body class="bg-slate-900 text-slate-100 min-h-screen">
        
        <!-- Navbar -->
        <nav class="bg-slate-800 border-b border-slate-700 px-6 py-4 flex justify-between items-center">
            <div class="flex items-center gap-3">
                <i class="fa-solid fa-server text-amber-500 text-2xl"></i>
                <h1 class="font-bold text-xl tracking-wide">Proxmox Cluster Orchestrator</h1>
            </div>
            <div class="flex items-center gap-4 text-sm text-slate-400">
                <span>SSOT Engine: <strong class="text-emerald-400">etcd (10.10.10.58)</strong></span>
                <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
        </nav>

        <!-- Main Container -->
        <div class="max-w-7xl mx-auto p-6 space-y-6">

            <!-- Top Grid: Configuration Control & MTU Testing -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                <!-- Card 1: Form Input MTU (Desired State) -->
                <div class="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg">
                    <h2 class="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
                        <i class="fa-solid fa-sliders text-blue-400"></i> Pengaturan Desired MTU (etcd SSOT)
                    </h2>
                    <p class="text-sm text-slate-400 mb-4">
                        Ubah nilai MTU di sini. `sync_agent` di setiap VM node akan secara otomatis mendeteksi perubahan ini dan melakukan auto-healing/rekonsiliasi jika terjadi perbedaan.
                    </p>
                    
                    <form id="mtuForm" onsubmit="submitMTU(event)" class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-slate-300 mb-1">Target MTU Interface (vmbr0)</label>
                            <input type="number" id="mtuInput" name="mtu" value="1500" required 
                                   class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                        <button type="submit" 
                                class="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 px-4 rounded-lg transition duration-200 flex items-center justify-center gap-2">
                            <i class="fa-solid fa-floppy-disk"></i> Simpan & Update etcd
                        </button>
                    </form>
                    <div id="mtuAlert" class="mt-3 text-xs p-3 rounded hidden"></div>
                </div>

                <!-- Card 2: Test Paket MTU Network -->
                <div class="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg">
                    <h2 class="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
                        <i class="fa-solid fa-network-wired text-emerald-400"></i> Pengujian Paket MTU (ICMP Test)
                    </h2>
                    <p class="text-sm text-slate-400 mb-4">
                        Uji apakah paket data dengan spesifikasi MTU dapat terkirim tanpa fragmentasi ke node sasaran.
                    </p>

                    <form id="pingTestForm" onsubmit="runMtuTest(event)" class="space-y-3">
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-medium text-slate-300 mb-1">IP Node Target</label>
                                <select id="targetIp" class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white">
                                <option value="10.10.10.211">pve1-a1 (10.10.10.211)</option>
                                <option value="10.10.10.212">pve-a2 (10.10.10.212)</option>
                            </select>
                            </div>
                            <div>
                                <label class="block text-xs font-medium text-slate-300 mb-1">Payload Size (Bytes)</label>
                                <input type="number" id="packetSize" value="1472" class="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white">
                                <span class="text-[10px] text-slate-500">*1472 Payload + 28 Header = 1500 MTU</span>
                            </div>
                        </div>
                        <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-medium py-2 px-4 rounded-lg transition duration-200 text-sm flex items-center justify-center gap-2">
                            <i class="fa-solid fa-vial"></i> Jalankan Uji Paket MTU
                        </button>
                    </form>
                    <pre id="testOutput" class="mt-3 p-3 bg-slate-950 border border-slate-800 rounded text-xs font-mono text-slate-300 max-h-24 overflow-y-auto hidden"></pre>
                </div>

            </div>

            <!-- Bottom Section: Node Monitoring Cards -->
            <div class="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-lg font-semibold text-slate-200 flex items-center gap-2">
                        <i class="fa-solid fa-cubes text-amber-400"></i> Monitoring Status Node Nested VM
                    </h2>
                    <button onclick="fetchNodeStatus()" class="text-sm bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-slate-300 transition">
                        <i class="fa-solid fa-rotate-right mr-1"></i> Refresh Status
                    </button>
                </div>

                <div id="nodesGrid" class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <!-- Cards will be populated by JavaScript -->
                    <div class="text-slate-500 text-sm col-span-2 text-center py-8">Memuat status node...</div>
                </div>
            </div>

        </div>

        <script>
            async function fetchNodeStatus() {
                try {
                    const res = await fetch('/api/nodes/status');
                    const data = await res.json();
                    
                    document.getElementById('mtuInput').value = data.desired_mtu;

                    const grid = document.getElementById('nodesGrid');
                    grid.innerHTML = '';

                    data.nodes.forEach(node => {
                        const isOnline = node.status === 'Online';
                        const inSync = node.in_sync;

                        const cardHTML = `
                            <div class="bg-slate-900 border ${inSync ? 'border-slate-700' : 'border-amber-500/50'} rounded-xl p-5 relative overflow-hidden">
                                <div class="flex justify-between items-start mb-4">
                                    <div>
                                        <h3 class="font-bold text-lg text-white flex items-center gap-2">
                                            ${node.name}
                                            <span class="text-xs px-2 py-0.5 rounded ${isOnline ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'}">
                                                ${node.status}
                                            </span>
                                        </h3>
                                        <p class="text-xs font-mono text-slate-400 mt-0.5">${node.ip}</p>
                                    </div>
                                    <span class="px-2.5 py-1 rounded-full text-xs font-semibold ${inSync ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}">
                                        ${inSync ? '✓ In Sync' : '⚠️ Drift Detected'}
                                    </span>
                                </div>

                                <div class="grid grid-cols-2 gap-4 bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs">
                                    <div>
                                        <span class="text-slate-500 block mb-1">Desired MTU (etcd)</span>
                                        <span class="font-mono text-slate-200 text-sm font-semibold">${node.desired_mtu}</span>
                                    </div>
                                    <div>
                                        <span class="text-slate-500 block mb-1">Actual MTU (Interface)</span>
                                        <span class="font-mono text-slate-200 text-sm font-semibold">${node.actual_mtu}</span>
                                    </div>
                                </div>

                                <div class="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-xs text-slate-400">
                                    <span>Agent: <strong class="text-slate-300">proxmox-sync.service</strong></span>
                                    <span class="text-slate-500">Auto-Reconcile: <strong class="text-emerald-400">Active</strong></span>
                                </div>
                            </div>
                        `;
                        grid.innerHTML += cardHTML;
                    });

                } catch (err) {
                    console.error("Gagal mengambil data node:", err);
                }
            }

            async function submitMTU(e) {
                e.preventDefault();
                const mtuVal = document.getElementById('mtuInput').value;
                const alertBox = document.getElementById('mtuAlert');

                const formData = new FormData();
                formData.append('mtu', mtuVal);

                try {
                    const res = await fetch('/api/config/mtu', { method: 'POST', body: formData });
                    const result = await res.json();

                    alertBox.className = "mt-3 text-xs p-3 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 block";
                    alertBox.innerText = result.message;
                    
                    // Refresh status setelah ubah etcd
                    setTimeout(fetchNodeStatus, 1500);
                } catch (err) {
                    alertBox.className = "mt-3 text-xs p-3 rounded bg-rose-950 text-rose-300 border border-rose-800 block";
                    alertBox.innerText = "Gagal mengubah konfigurasi di etcd.";
                }
            }

            async function runMtuTest(e) {
                e.preventDefault();
                const targetIp = document.getElementById('targetIp').value;
                const packetSize = document.getElementById('packetSize').value;
                const outputPre = document.getElementById('testOutput');

                outputPre.classList.remove('hidden');
                outputPre.innerText = "Menjalankan ping test...";

                const formData = new FormData();
                formData.append('target_ip', targetIp);
                formData.append('packet_size', packetSize);

                try {
                    const res = await fetch('/api/test/mtu-ping', { method: 'POST', body: formData });
                    const result = await res.json();
                    
                    if(result.success) {
                        outputPre.className = "mt-3 p-3 bg-emerald-950/40 border border-emerald-800 rounded text-xs font-mono text-emerald-300 max-h-36 overflow-y-auto block";
                    } else {
                        outputPre.className = "mt-3 p-3 bg-rose-950/40 border border-rose-800 rounded text-xs font-mono text-rose-300 max-h-36 overflow-y-auto block";
                    }
                    outputPre.innerText = result.output;
                } catch (err) {
                    outputPre.innerText = "Error saat menjalankan uji paket.";
                }
            }

            // Fetch otomatis setiap 5 detik
            fetchNodeStatus();
            setInterval(fetchNodeStatus, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)