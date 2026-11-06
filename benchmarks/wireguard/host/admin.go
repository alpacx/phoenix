package main

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"net/http/httputil"
	"net/netip"
	"net/url"
	"os"
	"phoenix-wgbench/internal/netstack"
	"strings"
	"time"
)

// Local development bridge. Only 127.0.0.1, no LAN listener and no arbitrary
// destination. The browser never receives the board's admin credential.
func serveAdmin(tnet *netstack.Net, address, tokenFile string) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil || host != "127.0.0.1" {
		return fmt.Errorf("admin listener must use 127.0.0.1")
	}
	b, err := os.ReadFile(tokenFile)
	if err != nil {
		return err
	}
	token := strings.TrimSpace(string(b))
	if len(token) != 64 || strings.Trim(token, "0123456789abcdef") != "" {
		return fmt.Errorf("invalid admin token file")
	}
	target, _ := url.Parse("http://10.77.0.2")
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.Transport = &http.Transport{DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
		return tnet.DialContextTCPAddrPort(ctx, netip.MustParseAddrPort("10.77.0.2:80"))
	}, ResponseHeaderTimeout: 15 * time.Second, DisableKeepAlives: true}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, e error) {
		http.Error(w, "Gateway unavailable; use http://192.168.9.1 on Phoenix-Test", 502)
	}
	original := proxy.Director
	proxy.Director = func(r *http.Request) {
		original(r)
		r.Host = "10.77.0.2"
		r.Header.Set("Authorization", "Bearer "+token)
		if r.Header.Get("Origin") != "" {
			r.Header.Set("Origin", "http://10.77.0.2")
		}
	}
	srv := &http.Server{Addr: address, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 20 * time.Second, WriteTimeout: 25 * time.Second, Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Host != address {
			http.Error(w, "Invalid host", 403)
			return
		}
		origin := r.Header.Get("Origin")
		if origin != "" && origin != "http://"+address {
			http.Error(w, "Invalid origin", 403)
			return
		}
		if r.Header.Get("Sec-Fetch-Site") == "cross-site" {
			http.Error(w, "Cross-site request denied", 403)
			return
		}
		if r.Method != "GET" && r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 16384)
		proxy.ServeHTTP(w, r)
	})}
	listener, err := net.Listen("tcp4", address)
	if err != nil {
		return err
	}
	go func() {
		if e := srv.Serve(listener); e != nil && e != http.ErrServerClosed {
			fmt.Fprintln(os.Stderr, "admin bridge stopped")
		}
	}()
	fmt.Println("Admin panel: http://" + address)
	return nil
}
