package main

import (
	"context"
	"crypto/ecdh"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/netip"
	"os"
	"path/filepath"
	"strings"
	"time"

	"golang.zx2c4.com/wireguard/conn"
	"golang.zx2c4.com/wireguard/device"
	"phoenix-wgbench/internal/netstack"
)

type Config struct{ HostPrivate, P4Public, Endpoint string }

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func main() {
	direct := flag.String("direct-listen", "", "optional LAN address for direct-mode comparison, only P4 source accepted")
	internet := flag.Bool("internet-exit", false, "enable public IPv4 TCP/UDP exit for authenticated P4 peer")
	gateway := flag.Bool("gateway-server", false, "serve browser benchmark inside tunnel for external gateway client")
	setup := flag.Bool("setup", false, "generate isolated test keys and firmware header")
	dir := flag.String("dir", "results/wgbench", "private local output directory")
	host := flag.String("host-ip", "192.168.8.103", "Mac LAN address")
	endpoint := flag.String("p4-ip", "192.168.8.170", "P4 LAN address")
	trials := flag.Int("trials", 3, "transfers per direction")
	reject := flag.Bool("test-rejected-source", false, "verify authenticated peer cannot use source 10.77.0.3")
	admin := flag.String("admin-listen", "", "optional loopback-only admin bridge (127.0.0.1:8085)")
	flag.Parse()
	if *setup {
		must(os.MkdirAll(*dir, 0700))
		if _, err := os.Stat(filepath.Join(*dir, "host.json")); err == nil {
			panic("test keys already exist; reuse or select a new directory")
		}
		hk, err := ecdh.X25519().GenerateKey(rand.Reader)
		must(err)
		pk, err := ecdh.X25519().GenerateKey(rand.Reader)
		must(err)
		c := Config{hex.EncodeToString(hk.Bytes()), hex.EncodeToString(pk.PublicKey().Bytes()), *endpoint + ":51820"}
		b, err := json.Marshal(c)
		must(err)
		must(os.WriteFile(filepath.Join(*dir, "host.json"), b, 0600))
		header := fmt.Sprintf("#define BENCH_P4_PRIVATE %q\n#define BENCH_HOST_PUBLIC %q\n#define BENCH_HOST_IP %q\n#define BENCH_EPOCH %d\n", base64.StdEncoding.EncodeToString(pk.Bytes()), base64.StdEncoding.EncodeToString(hk.PublicKey().Bytes()), *host, time.Now().Unix())
		must(os.WriteFile(filepath.Join(*dir, "bench_keys.h"), []byte(header), 0600))
		fmt.Println("Generated isolated test keys (not printed)")
		return
	}
	b, err := os.ReadFile(filepath.Join(*dir, "host.json"))
	must(err)
	var c Config
	must(json.Unmarshal(b, &c))
	source := "10.77.0.1"
	if *reject {
		source = "10.77.0.3"
	}
	tun, tnet, err := netstack.CreateNetTUN([]netip.Addr{netip.MustParseAddr(source)}, nil, 1420)
	must(err)
	dev := device.NewDevice(tun, conn.NewDefaultBind(), device.NewLogger(device.LogLevelError, "wgbench: "))
	defer dev.Close()
	must(dev.IpcSet(fmt.Sprintf("private_key=%s\nlisten_port=51821\npublic_key=%s\nallowed_ip=10.77.0.2/32\nendpoint=%s\npersistent_keepalive_interval=5\n", c.HostPrivate, c.P4Public, c.Endpoint)))
	must(dev.Up())
	go func() {
		for {
			time.Sleep(5 * time.Second)
			status, e := dev.IpcGet()
			if e != nil {
				return
			}
			for _, line := range strings.Split(status, "\n") {
				if strings.HasPrefix(line, "rx_bytes=") || strings.HasPrefix(line, "tx_bytes=") || strings.HasPrefix(line, "last_handshake_time_sec=") {
					fmt.Fprintln(os.Stderr, line)
				}
			}
		}
	}()

	fmt.Fprintln(os.Stderr, "Userspace WireGuard ready; no system routes changed")
	if *internet {
		if !*gateway {
			panic("internet-exit requires gateway-server")
		}
		stats, e := tnet.EnableInternetExit()
		must(e)
		fmt.Fprintln(os.Stderr, "Internet exit enabled: public IPv4 TCP/UDP through Mac sockets; no system route changes")
		go func() {
			for {
				time.Sleep(10 * time.Second)
				fmt.Fprintf(os.Stderr, "exit_tcp=%d exit_udp=%d exit_denied=%d exit_errors=%d\n", stats.TCP.Load(), stats.UDP.Load(), stats.Denied.Load(), stats.Errors.Load())
			}
		}()
	}
	if *gateway {
		if *admin != "" {
			must(serveAdmin(tnet, *admin, filepath.Join(*dir, "admin-token.txt")))
		}
		serveGateway(tnet, dev, *direct, c.Endpoint)
		return
	}
	if *reject {
		ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
		defer cancel()
		sock, e := tnet.DialContext(ctx, "tcp", "10.77.0.2:5001")
		if e == nil {
			sock.Close()
			panic("unauthorized source accepted")
		}
		status, e := dev.IpcGet()
		must(e)
		handshake := false
		for _, line := range strings.Split(status, "\n") {
			if strings.HasPrefix(line, "last_handshake_time_sec=") && line != "last_handshake_time_sec=0" {
				handshake = true
			}
		}
		if !handshake {
			panic("no handshake: rejection test inconclusive")
		}
		fmt.Println("Authenticated peer with unauthorized source: connection rejected (handshake verified)")
		return
	}

	// Allow the P4 boot/DHCP/handshake to finish, retry only the initial connection.
	deadline := time.Now().Add(60 * time.Second)
	for trial := 1; trial <= *trials; trial++ {
		for _, direction := range []byte{'U', 'D'} {
			var sock net.Conn
			for {
				ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
				sock, err = tnet.DialContext(ctx, "tcp", "10.77.0.2:5001")
				cancel()
				if err == nil {
					break
				}
				if trial != 1 || direction != 'U' || time.Now().After(deadline) {
					must(err)
				}
				fmt.Fprintln(os.Stderr, "Waiting for tunnel...")
				time.Sleep(time.Second)
			}
			must(sock.SetDeadline(time.Now().Add(125 * time.Second)))
			_, err = sock.Write([]byte{direction})
			must(err)
			start := time.Now()
			const size = 32 * 1024 * 1024
			if direction == 'U' {
				block := make([]byte, 8192)
				sent := 0
				for sent < size {
					n, e := sock.Write(block)
					must(e)
					if n == 0 {
						panic("zero write")
					}
					sent += n
				}
				var ack [4]byte
				_, err = io.ReadFull(sock, ack[:])
				must(err)
				if binary.BigEndian.Uint32(ack[:]) != size {
					panic("receiver count mismatch")
				}
			} else {
				n, e := io.CopyN(io.Discard, sock, size)
				must(e)
				if n != size {
					panic("truncated transfer")
				}
			}
			elapsed := time.Since(start).Seconds()
			must(sock.Close())
			must(json.NewEncoder(os.Stdout).Encode(map[string]any{"trial": trial, "direction": string(direction), "bytes": size, "seconds": elapsed, "mbps": size * 8 / elapsed / 1e6}))
			time.Sleep(time.Second)
		}
	}
	status, err := dev.IpcGet()
	must(err)
	for _, line := range strings.Split(status, "\n") {
		if strings.HasPrefix(line, "rx_bytes=") || strings.HasPrefix(line, "tx_bytes=") || strings.HasPrefix(line, "last_handshake_time_sec=") {
			fmt.Fprintln(os.Stderr, line)
		}
	}
}
