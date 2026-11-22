FROM phoenix-linux-test:local
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends iperf3 && rm -rf /var/lib/apt/lists/*
COPY start.sh /usr/local/bin/bench-peer
ENTRYPOINT ["sh", "/usr/local/bin/bench-peer"]
