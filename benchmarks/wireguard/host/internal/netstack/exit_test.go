package netstack

import (
	"context"
	"golang.zx2c4.com/wireguard/tun"
	"io"
	"net"
	"net/http"
	"net/netip"
	"os"
	"testing"
	"time"
)

func TestExitDestinationPolicy(t *testing.T) {
	for _, s := range []string{"127.0.0.1", "192.168.8.1", "10.77.0.1", "169.254.169.254", "100.64.0.1", "0.1.2.3", "192.0.2.1", "198.18.0.1", "224.0.0.1", "255.255.255.255", "::1", "::ffff:1.1.1.1"} {
		if publicDestination(netip.MustParseAddr(s)) {
			t.Errorf("allowed %s", s)
		}
	}
	for _, s := range []string{"1.1.1.1", "8.8.8.8"} {
		if !publicDestination(netip.MustParseAddr(s)) {
			t.Errorf("denied %s", s)
		}
	}
}
func TestExitDNSAndHTTPS(t *testing.T) {
	if os.Getenv("PHOENIX_EXIT_NETWORK_TEST") != "1" {
		t.Skip("explicit network integration test")
	}
	server, snet, e := CreateNetTUN([]netip.Addr{netip.MustParseAddr("10.77.0.1")}, nil, 1420)
	if e != nil {
		t.Fatal(e)
	}
	defer server.Close()
	client, cnet, e := CreateNetTUN([]netip.Addr{netip.MustParseAddr("10.77.0.2")}, []netip.Addr{netip.MustParseAddr("1.1.1.1")}, 1420)
	if e != nil {
		t.Fatal(e)
	}
	defer client.Close()
	stats, e := snet.EnableInternetExit()
	if e != nil {
		t.Fatal(e)
	}
	pump := func(dst, src tun.Device) {
		b := [][]byte{make([]byte, 65535)}
		sizes := make([]int, 1)
		for {
			_, e := src.Read(b, sizes, 0)
			if e != nil {
				return
			}
			if _, e = dst.Write([][]byte{b[0][:sizes[0]]}, 0); e != nil {
				return
			}
		}
	}
	go pump(server, client)
	go pump(client, server)
	transport := &http.Transport{DialContext: func(ctx context.Context, network, address string) (net.Conn, error) {
		return cnet.DialContext(ctx, "tcp4", address)
	}}
	defer transport.CloseIdleConnections()
	hc := &http.Client{Transport: transport, Timeout: 30 * time.Second}
	r, e := hc.Get("https://example.com/")
	if e != nil {
		t.Fatalf("%v TCP=%d UDP=%d denied=%d errors=%d", e, stats.TCP.Load(), stats.UDP.Load(), stats.Denied.Load(), stats.Errors.Load())
	}
	defer r.Body.Close()
	n, e := io.Copy(io.Discard, r.Body)
	if e != nil || r.StatusCode != 200 || n == 0 {
		t.Fatalf("HTTP status=%d bytes=%d err=%v", r.StatusCode, n, e)
	}
	if stats.TCP.Load() == 0 || stats.UDP.Load() == 0 {
		t.Fatal("TCP/DNS paths not exercised")
	}
	t.Logf("HTTPS certificate verified; response %d bytes; TCP=%d UDP=%d", n, stats.TCP.Load(), stats.UDP.Load())
}
