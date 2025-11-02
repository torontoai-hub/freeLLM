# FreeLLM Infrastructure Toolkit

A lightweight reference setup for running the FreeLLM proxy alongside a hardened vLLM server. The repository combines container configuration, metrics tooling, and automation to help you bootstrap a secure deployment quickly.

## Repository Layout

```
.
├── ansible/
│   ├── collections/         # Galaxy collection requirements
│   ├── inventory/           # Example inventory definitions
│   ├── playbooks/           # Entry-point playbooks (docker, firewall)
│   └── roles/               # Reusable automation roles
├── config.yaml              # FreeLLM proxy configuration
├── docker-compose.yml       # Local docker-compose example for the proxy stack
├── prometheus.yml           # Prometheus scrape configuration
└── README.md
```

## Prerequisites

- An Ubuntu 22.04/24.04 host that will run vLLM and the proxy.
- SSH access with a user that can escalate with `sudo` (default inventory user is `ubuntu`).
- Ansible 2.15+ on your control machine.
- Optional: NVIDIA GPU drivers and CUDA stack on the target if you plan to run GPU-backed models.

> **Tip:** Disable strict host key checking when iterating on a fresh machine: `export ANSIBLE_HOST_KEY_CHECKING=False`.

## Using the Ansible Automation

1. Install the required community collections:
   ```bash
   ansible-galaxy collection install -r ansible/collections/requirements.yml
   ```
2. Update `ansible/inventory/hosts.ini` with your host name or IP and SSH user.
3. Harden the host firewall and Docker networking:
   ```bash
   ansible-playbook \
     -i ansible/inventory/hosts.ini \
     ansible/playbooks/harden_firewall.yml \
     --private-key ~/workspace/<private key>.pem
   ```
4. Install Docker CE and supporting packages:
   ```bash
   ansible-playbook \
     -i ansible/inventory/hosts.ini \
     ansible/playbooks/install_docker.yml \
     --private-key ~/workspace/<private key>.pem
   ```

Role defaults keep SSH (TCP/22) open and lock down the proxy port (TCP/8001) to the CIDR list you supply via `allowed_8001_cidrs`. Override these variables in your inventory or on the command line to match your environment.

## Running the FreeLLM Proxy Locally

Bring the proxy stack up with Docker Compose (includes Redis and optional metrics exporters):
```bash
docker compose up -d
```

Test the API once the stack is up:
```bash
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer torontoai"

curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer torontoai" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "Explain vector databases in two sentences."}]
  }'
```

## Running vLLM with Docker

Use the official image to start a GPU-enabled vLLM instance:
```bash
docker run --runtime nvidia --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  --env "HF_TOKEN=$HF_TOKEN" \
  -p 8000:8000 \
  --ipc=host \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen3-0.6B
```

With Docker, firewall hardening, and the proxy configuration in place, you have the building blocks needed to host and secure a private LLM service.
