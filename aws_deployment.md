# AWS Deployment Documentation: College Happiness App

## Overview
This document outlines the infrastructure design and deployment steps taken to host the "College Happiness" Python application on AWS. The architecture was chosen to balance **cost-efficiency** (Free Tier optimization) with **production-grade reliability**.

---

## Infrastructure Selection: 
I deliberately moved away from standard defaults to optimize for performance and budget.

* **Instance Type: `t4g.micro`**
    * **Why:** We chose AWS Graviton (ARM64) processors instead of standard Intel (`t2` or `t3`) instances. `t4g` instances are roughly **20% cheaper** and offer better performance per dollar.
* **OS: `Ubuntu LTS (ARM64)`**
    * **Why:** Ubuntu provides the most package compatibility for Python/Machine Learning stacks.
* **Storage: `8GB gp3`**
    * **Why:** The default 30GB is unnecessary for the app. Downgrading to 8GB reduces monthly EBS storage costs while still providing ample room for the data and processing.

## Network Architecture 
Instead of using the default VPC, I manually configured the network to ensure secure connectivity.

* **`VPC & Subnets:`** Created a custom Virtual Private Cloud to isolate resources.
* **`Internet Gateway (IGW):`** Attached to the VPC to allow traffic to enter/exit the network.
* **`Route Tables:`** Manually configured the route `0.0.0.0/0 -> IGW`.
    * **Why:** Without this explicit route, the server could receive requests but had no map to send the return traffic back to the internet.

## Security & Access Control
Implemented a "Least Privilege" security approach using AWS Security Groups.

* **Inbound Rules:**
    * **`Port 22 (SSH):`** Allowed for remote administration.
    * **`Port 80 (HTTP):`** Allowed for public web traffic.
    * **`All Other Ports:`** Blocked by default to prevent unauthorized access.
* **Authentication:** Used **SSH Key Pairs (`.pem`)** instead of password login to prevent attacks.

## Server Optimization: 
Since `t4g.micro` instances have limited RAM (1GB) and the app uses heavy libraries like `pandas` and `scikit-learn`, memory management was critical.

* **Swap Space (2GB):**
    * **Action:** Allocated a 2GB file on the hard drive to act as "emergency RAM."
    * **Why:** If the application spikes in memory usage, the OS would move inactive data to the hard drive instead of crashing the server.

## Application Deployment
* **Version Control:** Code was pulled securely from GitHub using **Personal Access Tokens (PAT)**.
* **Virtual Environment:**
    * **Why:** Isolated Python dependencies inside a specific folder to prevent conflicts with system-level packages.


* **`Gunicorn:`** Used as the WSGI HTTP Server to handle multiple worker threads.
* **Systemd Service (`happiness.service`):**
    * **Why:** Configured the app as a background Linux service. This ensures the app **automatically restarts** if the server reboots or if the code crashes, allowing for 24/7 availability.

## Web Server Configuration 
* **`Reverse Proxy:`** Set up Nginx to sit in front of Gunicorn.
    * **Why:** Gunicorn is great for Python, but weak at handling direct internet traffic. Nginx handles the heavy lifting (buffering, slow clients, static files) and forwards safe requests to the Python app through a Unix Socket.
* **`Permissions Fix:`** Adjusted directory permissions (`chmod 755`) to allow the Nginx user (`www-data`) to access the application socket file.

## Cost Auditing
* **`Action:`** Terminated all "Zombie Resources" to prevent unnecessary charges, ensuring the project remains strictly within my planned budget.
