tun.go derived from wireguard-go v0.0.0-20261024220952-b3bc704ef0ee, tun/netstack/tun.go (MIT).
Local change: HandleLocal=false, required with promiscuous NIC to avoid classifying every remote source as local.
Local addition exit.go provides bounded public IPv4 TCP/UDP socket relay; no host OS routing changes.
