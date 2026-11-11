FROM phoenix-linux-test:local
RUN apt-get update && apt-get install -y --no-install-recommends qemu-system-arm linux-image-arm64 initramfs-tools e2fsprogs cpio && rm -rf /var/lib/apt/lists/*
