
<img width="2752" height="1361" alt="nous" src="https://github.com/user-attachments/assets/3780b1f3-087e-4a68-bd78-d7ee3f458b69" />

#  DEVORUN ORACLE RADAR: Next-Gen Crypto Intelligence Terminal

Devorun Oracle Radar is an autonomous, terminal-based intelligence engine that tracks critical crypto, hack, and market movements on X (Twitter) in real-time, seamlessly bypassing API restrictions using the Nitter infrastructure. 

This project is much more than a standard scraping tool; it is a self-healing, cache-busting "Cyberpunk" command center that consumes almost zero system resources.

###  Core Features & Tech Stack
* **Visual Interface (UI):** Built with Python's `rich` library, it features a continuously updating (Live Display), flicker-free, cyberpunk-themed dynamic table right in the terminal.
* **Smart Signal Filtering:** Incoming data isn't static. Tweets containing specific target keywords (e.g., *btc, sol, hack, exploit, pump*) are instantly flagged as **🚨 CRITICAL** (Red), while other updates remain in the live feed as **[INFO]** (Blue/White).
* **Autonomous Logging (Ultra-Light):** The terminal feed is asynchronously appended to a `radar_history.txt` file in the background. This ensures 24/7 historical logging without stressing the CPU or RAM.
* **Audio Alert System:** When a critical signal drops, the system triggers a non-blocking hardware-level 'beep' to instantly alert the user, even if they are away from the screen.

---

###  Challenges Faced & "Hacker" Solutions

During development, we utilized Nitter (an open-source X front-end) RSS networks to escape the severe limitations and costs of traditional APIs. However, this brought significant technical hurdles. Here is the log of how we bypassed those roadblocks:

#### 1. The "Ghost Account" and Nitter Cache Issue
* **The Problem:** While data from giant accounts like Elon Musk or Vitalik Buterin hit the terminal instantly, test tweets from smaller target accounts wouldn't show up. Nitter servers were pushing these smaller accounts to the background and serving stale, cached data.
* **The Solution (Cache Breaker):** We injected a dynamic timestamp query (`?t=TIMESTAMP`) at the end of the RSS URLs for every request. This **"Cache Breaker"** tactic forced the Nitter servers to bypass their cache and fetch fresh data every single time, instantly integrating all accounts into the live radar.

#### 2. HTTP 403 / 502 Errors & "Rate Limit" Roadblocks
* **The Problem:** Due to high-frequency polling (30-second loops), Nitter servers flagged the system as a bot attack, throwing `HTTP 403 (Forbidden)` and `HTTP 502 (Bad Gateway)` errors. The screen would freeze on "Awaiting signal" or "SOURCE OFFLINE" states.
* **The Solution (Stealth Mode & Fallback Logic):** Instead of relying on a single Nitter server, we built a multi-server pool using globally active nodes. We added randomized **User-Agent** headers to every request to mimic real browser traffic. If a server blocked us, the code wouldn't crash; a **"Smart Retry"** algorithm instantly pivoted to the next available server in the pool.

#### 3. Synchronization and Data Bottlenecks
* **The Problem:** Scanning multiple accounts simultaneously meant that a network timeout or failure on just one account would leave the entire terminal table empty, waiting for the slow request to finish.
* **The Solution (Partial Rendering & Auto-Recovery):** We switched to an asynchronous "render whoever arrives first" (Partial Data Fetching) logic instead of waiting for all data to load perfectly. Furthermore, we implemented an **Auto-Recovery** system. If the internet disconnects, the system goes into a graceful standby mode and seamlessly resumes fetching once the connection is restored.
