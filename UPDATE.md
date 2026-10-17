# Update Log: Remote Access, Network Binding & Data Optimization

This document outlines the architecture, challenges encountered, and engineering solutions implemented to enable secure, remote mobile access to the EGX Terminal via a private mesh network without compromising local security, battery life, or mobile cellular data.

---

## 1. Objective & Requirements

* **Primary Goal**: Allow the user to run the EGX Terminal on a host PC and monitor live prices from a mobile device (phone/tablet) anywhere in the world.
* **Security & Privacy**:
  * Zero public exposure: No port forwarding on the home router, no public cloud intermediaries, and no open web vulnerability footprint.
  * Secrets safety: No personal identifiers, API credentials, or internal network IPs committed to version control.
* **Resource Optimization**:
  * Protect limited cellular data quotas from constant background streaming when the phone screen is locked.
  * Headless host capability: Host laptop must be able to stay active and stream data with the screen closed.

---

## 2. Technical Challenges & Root-Cause Analysis

### Issue A: Loopback Address Isolation (`127.0.0.1` vs `0.0.0.0`)
* **Symptom**: When attempting to reach the server from the phone's browser, the connection failed with:
  > *"The connection has timed out"*
* **Underlying Mechanism**:
  * In networking, `127.0.0.1` represents the **Loopback Interface** (`lo`). Sockets bound to `127.0.0.1` only accept TCP packets generated from within the local operating system itself.
  * Packets arriving from virtual private network (VPN) adapters or local area network (LAN) interfaces carry external destination IPs (such as the node's VPN mesh IP). When the host OS receives a packet targeting a non-loopback IP, it checks for active listeners on that specific IP or `0.0.0.0`. Because the server was bound only to `127.0.0.1`, the kernel dropped external packets.
* **Why the Standalone Executable Used `127.0.0.1`**:
  * In development, configuration settings are parsed from the local `.env` file. However, when packaged into a standalone PyInstaller binary (`dist/EGX_Tracker.exe`), the executable executed from the `dist/` subfolder, where no `.env` file was present. Consequently, the backend silently fell back to its default host setting (`127.0.0.1`).

---

### Issue B: Silent Packet Dropping by OS Firewall
* **Symptom**: Mobile browser displayed a connection timeout after waiting 15–30 seconds, rather than an immediate *"Connection refused"*.
* **Underlying Mechanism**:
  * When a destination port has no service listening, the operating system kernel typically returns an immediate **TCP RST** (Reset) flag, prompting the client browser to report *"Connection refused"*.
  * A **timeout**, conversely, signifies that packets are arriving at the network interface but being silently discarded without an acknowledgement or reset. This is the hallmark behavior of the host operating system's stateful packet inspection firewall (Windows Defender Firewall).
  * Windows categorizes network connections into profiles: **Domain**, **Private**, and **Public**. While VPN mesh interfaces are classified as `Private`, Windows defaults to dropping inbound traffic on newly opened TCP ports unless an explicit Inbound Allow Rule exists for that port or application binary.

---

### Issue C: Hardcoded Frontend Host & WebSocket Endpoints
* **Symptom**: If the frontend bundle was loaded on another device, API requests and WebSocket streams continued attempting to reach `http://127.0.0.1:8000/ws`.
* **Underlying Mechanism**:
  * Client-side single-page applications (SPAs) execute entirely within the client's browser engine.
  * When a mobile device executes code referencing `127.0.0.1`, it attempts to communicate with *itself* (the phone's internal loopback), failing to reach the host computer.

---

## 3. Implemented Solutions

```
+-----------------------------------------------------------------------------------+
|                                Private Mesh Network                               |
|                                                                                   |
|   +-----------------------+                    +------------------------------+   |
|   |     Mobile Phone      |                    |         Host Machine         |   |
|   |  (End-to-End Encrypted)                    |      (Headless / Laptop)     |   |
|   |                       |                    |                              |   |
|   |  - Dynamic Host URL   |     Encrypted      |  - Bound: 0.0.0.0:8000       |   |
|   |  - Page Visibility API|  WireGuard Tunnel  |  - Inbound Port 8000 Allow   |   |
|   |  - Data Saver Pauser  | <================> |  - Access Audit Logger       |   |
|   |  - Standalone PWA UI  |                    |  - Live WebSocket Dispatch   |   |
|   +-----------------------+                    +------------------------------+   |
+-----------------------------------------------------------------------------------+
```

### 1. Multi-Interface Server Binding & Dynamic `.env` Discovery
* **Default Host Updated**:
  * Modified `backend/app/config.py` to default `HOST="0.0.0.0"`. `0.0.0.0` (`INADDR_ANY`) instructs the operating system to listen on all active network interfaces simultaneously, allowing both local access (`http://localhost:8000`) and private mesh access.
* **Hierarchical Environment File Search**:
  * Updated `.env` path resolution to inspect multiple candidate directories:
    ```python
    candidate_env_paths = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / ".env",  # Handles execution from dist/
        BACKEND_DIR / ".env",
        Path(sys.executable).resolve().parent / ".env",
    ]
    ```

---

### 2. Client-Side Dynamic Origin & Protocol Resolution
* In `frontend/src/hooks/useEGXWebSocket.js` and `frontend/src/components/StockSearchModal.jsx`, replaced all hardcoded localhost references with dynamic browser window evaluation:
  ```javascript
  const getWsUrl = () => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host; // Automatically resolves to localhost or VPN IP
    return `${protocol}//${host}/ws`;
  };
  ```
* **Adaptive Network Badge**:
  * The terminal header automatically detects the network type. When accessed via mesh VPN ranges (e.g. `100.x.x.x`), it displays an active `Tailscale Mesh` indicator alongside the host address.

---

### 3. Cellular Data & Battery Saver (Page Visibility API)
To prevent continuous background streaming over limited mobile cellular quotas:
* **Visibility State Detection**:
  * Attached an event listener to `document.addEventListener("visibilitychange", ...)` inside the WebSocket hook.
* **Intelligent Stream Control**:
  * **Screen Off / Tab Minimized**: The frontend dispatches a lightweight `{"action": "pause"}` message to the backend. The backend suspends upstream WebSocket price ticks to the client, idling the connection and dropping network data consumption to near zero.
  * **Screen Unlocked / Tab Restored**: The frontend transmits `{"action": "resume"}` followed by a request for a fresh market snapshot, instantly updating all quotes without requiring a full page reload.

---

### 4. Inbound Network Access Logging
* Implemented an asynchronous HTTP middleware in `backend/main.py`:
  * Logs the client's IP address, HTTP method, URL path, HTTP status code, and execution latency.
  * Filters out routine internal health checks (`/api/status`) from flooding logs while capturing external connection requests.
* Added connection lifecycle logging for WebSockets:
  * Records connecting and disconnecting client IPs directly to the local persistent log file (`egx_launcher.log`).

---

### 5. Automated Firewall Configuration Script
* Created `Allow_Firewall_Access.bat`:
  * A 1-click administrative batch script that configures Windows Defender Firewall.
  * Restricts incoming traffic permissions specifically to **Private** and **Domain** network profiles (blocking public Wi-Fi access).
  * Automatically excluded from Git via `.gitignore` to protect personal deployment details.

---

## 4. Security & Safety Checklist

| Feature | Implementation | Security Benefit |
| :--- | :--- | :--- |
| **No Port Forwarding** | Private Mesh (WireGuard) | Zero attack surface exposed to the public internet. |
| **Profile Isolation** | Private Network Only | Port 8000 is blocked if connecting to open/public Wi-Fi. |
| **Repo Sanitization** | Strict `.gitignore` | Private IPs, credentials, `.env`, `.db`, and `.bat` are never pushed. |
| **Wildcard CORS Safety** | Private IP Scoping | Dynamic CORS wildcard is only active when bound to `0.0.0.0` / VPN ranges. |
| **Data Protection** | Visibility State Pausing | Background mobile data transfer is eliminated upon screen lock. |

---

## 5. Verification & Testing

1. **Local Desktop**: Launched standalone `dist/EGX_Tracker.exe` — verified app mode window opens and binds to `0.0.0.0:8000`.
2. **Mobile Browser**: Navigated to host VPN IP via phone browser — verified full terminal UI renders with real-time quote updates.
3. **Data Saver Test**: Locked phone screen and observed log activity; verified stream pause acknowledgment and immediate resumption upon unlock.
4. **Clean Exit**: Closed desktop window on host machine; verified complete teardown of server processes with zero lingering ports.
