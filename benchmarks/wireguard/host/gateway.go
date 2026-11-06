package main

import (
	"encoding/json"
	"fmt"
	"golang.zx2c4.com/wireguard/device"
	"io"
	"net"
	"net/http"
	"os"
	"phoenix-wgbench/internal/netstack"
	"strings"
	"sync/atomic"
	"time"
)

// Tunnel-only test listener; optional Internet exit is configured separately.
func serveGateway(tnet *netstack.Net, dev *device.Device, direct, peerEndpoint string) {
	var cutting atomic.Bool
	log := func(v any) { b, _ := json.Marshal(v); fmt.Println(string(b)) }
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		page := gatewayPage
		if r.Header.Get("X-Phoenix-Direct") == "1" {
			page = strings.ReplaceAll(page, "Phoenix: firewall + VPN", "Phoenix: confronto senza VPN")
			page = strings.ReplaceAll(page, "Questa pagina è servita dal Mac attraverso WireGuard. Il telefono usa l’hotspot della Waveshare.", "Prova temporanea senza VPN: Wi-Fi → firewall/NAT → Ethernet → Mac. Ripristino VPN automatico dopo 5 minuti.")
		}
		io.WriteString(w, page)
	})
	mux.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		io.WriteString(w, "tunnel-ok")
	})
	mux.HandleFunc("/download", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Type", "application/octet-stream")
		w.Header().Set("Content-Length", "8388608")
		start := time.Now()
		block := make([]byte, 16384)
		total := 0
		for total < 8388608 {
			n, e := w.Write(block)
			total += n
			if e != nil {
				break
			}
		}
		log(map[string]any{"event": "download_server", "bytes": total, "seconds": time.Since(start).Seconds()})
	})
	mux.HandleFunc("/upload", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		start := time.Now()
		n, e := io.Copy(io.Discard, http.MaxBytesReader(w, r.Body, 8388608))
		if e != nil || n != 8388608 {
			http.Error(w, "incomplete", 400)
			return
		}
		log(map[string]any{"event": "upload_server", "bytes": n, "seconds": time.Since(start).Seconds()})
		json.NewEncoder(w).Encode(map[string]any{"bytes": n})
	})
	mux.HandleFunc("/result", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		var v map[string]any
		if json.NewDecoder(http.MaxBytesReader(w, r.Body, 16384)).Decode(&v) != nil {
			w.WriteHeader(400)
			return
		}
		log(map[string]any{"event": "browser_result", "result": v, "remote": r.RemoteAddr})
		io.WriteString(w, "saved")
	})
	mux.HandleFunc("/cut", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		if !cutting.CompareAndSwap(false, true) {
			w.WriteHeader(409)
			return
		}
		io.WriteString(w, "VPN will stop in 2 seconds, restart after 15 seconds")
		go func() {
			defer cutting.Store(false)
			time.Sleep(2 * time.Second)
			must(dev.Down())
			log(map[string]any{"event": "vpn_down", "time": time.Now()})
			time.Sleep(15 * time.Second)
			must(dev.Up())
			log(map[string]any{"event": "vpn_up", "time": time.Now()})
		}()
	})
	if direct != "" {
		peerIP, _, e := net.SplitHostPort(peerEndpoint)
		must(e)
		dl, e := net.Listen("tcp4", direct)
		must(e)
		go func() {
			srv := &http.Server{ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 120 * time.Second, WriteTimeout: 120 * time.Second, Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				source, _, _ := net.SplitHostPort(r.RemoteAddr)
				if source != peerIP || r.URL.Path == "/cut" {
					http.Error(w, "forbidden", 403)
					return
				}
				r.Header.Set("X-Phoenix-Direct", "1")
				mux.ServeHTTP(w, r)
			})}
			if e := srv.Serve(dl); e != nil {
				fmt.Fprintln(os.Stderr, "direct listener stopped:", e)
			}
		}()
		fmt.Fprintln(os.Stderr, "Direct comparison listener:", direct, "restricted to P4 source")
	}
	listener, e := tnet.ListenTCP(&net.TCPAddr{IP: net.ParseIP("10.77.0.1"), Port: 8080})
	must(e)
	fmt.Fprintln(os.Stderr, "Gateway browser test ready: http://10.77.0.1:8080 (inside WireGuard only)")
	must((&http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 120 * time.Second, WriteTimeout: 120 * time.Second}).Serve(listener))
}

const gatewayPage = `<!doctype html><html lang="it"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>Phoenix — prova gateway</title><style>body{font:17px system-ui;max-width:720px;margin:30px auto;padding:20px;background:#101720;color:#edf5ff}button{padding:14px;margin:8px 0;width:100%;font:inherit}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#b3c6da}</style><h1>Phoenix: firewall + VPN</h1><p>Questa pagina è servita dal Mac attraverso WireGuard. Il telefono usa l’hotspot della Waveshare.</p><small>Prova locale: non misura Internet né USB. Lascia questa pagina aperta. Disattiva i dati mobili per evitare connessioni alternative.</small><button id="speed">Misura: 3 prove da 8 MiB per direzione</button><button id="cut">Interrompi VPN per 15 secondi e verifica recupero</button><button id="stress">Prova prolungata: 10 minuti (traffico locale)</button><pre id="out">Pronto.</pre><script>
const out=document.querySelector('#out');const say=t=>out.textContent+='\n'+t;
async function report(v){await fetch('/result',{method:'POST',body:JSON.stringify(v),headers:{'Content-Type':'application/json'}})}
async function req(path,options={}){let r=await fetch(path,{cache:'no-store',...options,signal:AbortSignal.timeout(120000)});if(!r.ok)throw Error('HTTP '+r.status);return r}
function busy(v){speed.disabled=cut.disabled=stress.disabled=v}
speed.onclick=async()=>{busy(true);out.textContent='Misura in corso…';try{let results=[];for(let i=1;i<=3;i++)for(let direction of ['download','upload']){let payload=direction==='upload'?new Uint8Array(8388608):null;let t=performance.now();let r=await req('/'+direction,payload?{method:'POST',body:payload}:{});let n;if(payload){n=(await r.json()).bytes}else{n=(await r.arrayBuffer()).byteLength}if(n!==8388608)throw Error('Trasferimento incompleto');let seconds=(performance.now()-t)/1000;let v={trial:i,direction,bytes:n,seconds,mbps:n*8/seconds/1e6};results.push(v);say(i+' '+direction+': '+v.mbps.toFixed(2)+' Mbit/s');await report(v)}for(let direction of ['download','upload']){let a=results.filter(v=>v.direction===direction);say('Media aggregata '+direction+': '+(a.reduce((s,v)=>s+v.bytes,0)*8/a.reduce((s,v)=>s+v.seconds,0)/1e6).toFixed(2)+' Mbit/s')}say('Misura completata.')}catch(e){say('PROVA NON COMPLETATA: '+e.message);try{await report({error:e.message})}catch{}}finally{busy(false)}};
cut.onclick=async()=>{busy(true);out.textContent='Interruzione controllata del peer VPN…';let results=[];try{await req('/cut',{method:'POST'});let start=performance.now();while(performance.now()-start<35000){let t=(performance.now()-start)/1000;let ok=false;try{let r=await fetch('/ping?'+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(1500)});ok=r.ok}catch{}results.push({seconds:t,ok});say(t.toFixed(1)+' s: '+(ok?'tunnel raggiungibile':'nessuna risposta'));await new Promise(r=>setTimeout(r,700))}await report({test:'peer_outage',samples:results});say('Risultati salvati sul Mac. Il controllo delle fughe richiede anche i log di rete.')}catch(e){say(e.message)}finally{busy(false)}};
stress.onclick=async()=>{busy(true);out.textContent='Prova prolungata in corso: tieni questa pagina in primo piano.';let start=performance.now(),cycle=0;try{while(performance.now()-start<600000){cycle++;for(let direction of ['download','upload']){let t=performance.now();let r=await req('/'+direction,direction==='upload'?{method:'POST',body:new Uint8Array(8388608)}:{});let n=direction==='upload'?(await r.json()).bytes:(await r.arrayBuffer()).byteLength;if(n!==8388608)throw Error('Trasferimento incompleto');let seconds=(performance.now()-t)/1000;let v={test:'endurance',cycle,direction,bytes:n,seconds,mbps:n*8/seconds/1e6};await report(v);say(cycle+' '+direction+': '+v.mbps.toFixed(2)+' Mbit/s')}await new Promise(r=>setTimeout(r,5000))}await report({test:'endurance_complete',cycles:cycle,seconds:(performance.now()-start)/1000});say('Prova prolungata completata.')}catch(e){say('PROVA NON COMPLETATA: '+e.message);try{await report({test:'endurance_error',error:e.message})}catch{}}finally{busy(false)}};
</script></html>`
