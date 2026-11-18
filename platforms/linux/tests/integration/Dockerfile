FROM debian:bookworm-slim
# Userspace tools the Rust services drive on the target, plus test fixtures
# (python3 http.server/TLS fixture, busybox udhcpc as DHCP client).
RUN apt-get update && apt-get install -y --no-install-recommends python3 nftables iproute2 wireguard-tools iputils-ping conntrack curl ca-certificates hostapd dnsmasq-base systemd network-manager dbus openssl busybox && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
