FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 nftables iproute2 wireguard-tools iputils-ping conntrack curl ca-certificates hostapd dnsmasq-base systemd network-manager dbus openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/workspace/platforms/linux/service
CMD ["python3", "platforms/linux/tests/integration/check_kernel.py"]
