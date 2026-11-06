package netstack

import (
	"fmt"
	"gvisor.dev/gvisor/pkg/tcpip/adapters/gonet"
	"gvisor.dev/gvisor/pkg/tcpip/stack"
	"gvisor.dev/gvisor/pkg/tcpip/transport/tcp"
	"gvisor.dev/gvisor/pkg/tcpip/transport/udp"
	"gvisor.dev/gvisor/pkg/waiter"
	"io"
	"net"
	"net/netip"
	"strconv"
	"sync/atomic"
	"time"
)

// ExitStats intentionally contains no browsing destinations or DNS query names.
type ExitStats struct {
	TCP    atomic.Uint64
	UDP    atomic.Uint64
	Denied atomic.Uint64
	Errors atomic.Uint64
}

var excluded = []netip.Prefix{
	netip.MustParsePrefix("0.0.0.0/8"), netip.MustParsePrefix("100.64.0.0/10"),
	netip.MustParsePrefix("192.0.0.0/24"), netip.MustParsePrefix("192.0.2.0/24"),
	netip.MustParsePrefix("198.18.0.0/15"), netip.MustParsePrefix("198.51.100.0/24"),
	netip.MustParsePrefix("203.0.113.0/24"), netip.MustParsePrefix("240.0.0.0/4"),
}

func publicDestination(a netip.Addr) bool {
	if !a.Is4() || !a.IsGlobalUnicast() || a.IsPrivate() || a.IsLoopback() || a.IsLinkLocalUnicast() {
		return false
	}
	for _, p := range excluded {
		if p.Contains(a) {
			return false
		}
	}
	return true
}

// EnableInternetExit relays authenticated tunnel TCP/UDP via ordinary host sockets.
// No routing or packet forwarding is enabled in the host OS. Private destinations
// remain inaccessible; only the existing tunnel-local browser listener is local.
func (n *Net) EnableInternetExit() (*ExitStats, error) {
	if e := n.stack.SetPromiscuousMode(1, true); e != nil {
		return nil, fmt.Errorf("promiscuous: %v", e)
	}
	if e := n.stack.SetSpoofing(1, true); e != nil {
		return nil, fmt.Errorf("spoofing: %v", e)
	}
	stats := new(ExitStats)
	slots := make(chan struct{}, 256)
	destination := func(id stack.TransportEndpointID) (string, bool) {
		a, ok := netip.AddrFromSlice(id.LocalAddress.AsSlice())
		src, _ := netip.AddrFromSlice(id.RemoteAddress.AsSlice())
		if !ok || src != netip.MustParseAddr("10.77.0.2") || !publicDestination(a) || id.LocalPort == 0 {
			stats.Denied.Add(1)
			return "", false
		}
		return net.JoinHostPort(a.String(), strconv.Itoa(int(id.LocalPort))), true
	}
	acquire := func() bool {
		select {
		case slots <- struct{}{}:
			return true
		default:
			stats.Denied.Add(1)
			return false
		}
	}
	tf := tcp.NewForwarder(n.stack, 0, 64, func(r *tcp.ForwarderRequest) {
		dst, ok := destination(r.ID())
		if !ok || !acquire() {
			r.Complete(true)
			return
		}
		defer func() { <-slots }()
		upstream, e := net.DialTimeout("tcp4", dst, 8*time.Second)
		if e != nil {
			stats.Errors.Add(1)
			r.Complete(true)
			return
		}
		defer upstream.Close()
		var wq waiter.Queue
		ep, te := r.CreateEndpoint(&wq)
		if te != nil {
			stats.Errors.Add(1)
			r.Complete(true)
			return
		}
		r.Complete(false)
		downstream := gonet.NewTCPConn(&wq, ep)
		defer downstream.Close()
		stats.TCP.Add(1)
		// Bounded bench sessions; relay preserves TLS end-to-end, no HTTP interception.
		upstream.SetDeadline(time.Now().Add(10 * time.Minute))
		downstream.SetDeadline(time.Now().Add(10 * time.Minute))
		done := make(chan struct{})
		go func() {
			io.Copy(upstream, downstream)
			if c, ok := upstream.(*net.TCPConn); ok {
				c.CloseWrite()
			}
			close(done)
		}()
		io.Copy(downstream, upstream)
		downstream.Close()
		upstream.Close()
		<-done
	})
	n.stack.SetTransportProtocolHandler(tcp.ProtocolNumber, tf.HandlePacket)
	uf := udp.NewForwarder(n.stack, func(r *udp.ForwarderRequest) {
		dst, ok := destination(r.ID())
		if !ok || !acquire() {
			return
		}
		// Create synchronously: UDP request packet is owned by the input callback.
		var wq waiter.Queue
		ep, e := r.CreateEndpoint(&wq)
		if e != nil {
			<-slots
			stats.Errors.Add(1)
			return
		}
		downstream := gonet.NewUDPConn(&wq, ep)
		go func() {
			defer func() { <-slots }()
			defer downstream.Close()
			upstream, e := net.DialTimeout("udp4", dst, 5*time.Second)
			if e != nil {
				stats.Errors.Add(1)
				return
			}
			defer upstream.Close()
			stats.UDP.Add(1)
			relay := func(dst, src net.Conn) {
				buf := make([]byte, 65535)
				for {
					src.SetReadDeadline(time.Now().Add(30 * time.Second))
					count, e := src.Read(buf)
					if e != nil {
						return
					}
					dst.SetWriteDeadline(time.Now().Add(5 * time.Second))
					if _, e = dst.Write(buf[:count]); e != nil {
						return
					}
				}
			}
			done := make(chan struct{})
			go func() { relay(upstream, downstream); upstream.Close(); close(done) }()
			relay(downstream, upstream)
			downstream.Close()
			upstream.Close()
			<-done
		}()
	})
	n.stack.SetTransportProtocolHandler(udp.ProtocolNumber, uf.HandlePacket)
	return stats, nil
}
