# FreeLLM

A lightweight LLM Proxy for Everyday Developers

export ANSIBLE_HOST_KEY_CHECKING=False
ansible-playbook -i hosts.ini firewall_config.yaml \
  --private-key ~/workspace/<private key>.pem \
  -u ubuntu


curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer torontoai"


curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer torontoai" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "Explain vector databases in two sentences."}]
  }'


docker run --runtime nvidia --gpus all     -v ~/.cache/huggingface:/root/.cache/huggingface     --env "HF_TOKEN=$HF_TOKEN"     -p 8000:8000     --ipc=host     vllm/vllm-openai:latest     --model Qwen/Qwen3-0.6B