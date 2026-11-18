# USB Ethernet — prova fisica ROCK 4C+ e limiti di banco

Aggiornamento banco 2026-11-15: il gadget Radxa preesistente è stato enumerato
dal Mac attraverso hub USB2/A–A. La sostituzione con Phoenix ha evidenziato
incompatibilità reali corrette nel codice: `ifname` richiede un template `%d`
(si configura `phusb0`, il programma scrive `phusb%d` e verifica il nome
allocato); l'unbind di un gadget mai associato restituisce ENODEV e va evitato.
La successiva attivazione Phoenix ha verificato DHCP, HTTPS via USB e uscita
NordVPN, incluso blocco senza tunnel e riconnessione automatica. Vedere
BRINGUP.md della ROCK per misure e limiti.

## Eccezione esplicita di banco, senza misura VBUS

Non equivale a `vbus_verified`. Solo per la ROCK 4C+ di questo banco, con
accettazione esplicita del rischio residuo da parte dell'operatore:
`bench_unmeasured_vbus: true` consente l'avvio soltanto se il file regolare
root-only `/run/phoenix-usb-bench.json` contiene il boot_id corrente, la UDC
fe800000.usb e `acknowledge_unmeasured_vbus: true`. Il codice controlla modello,
nodo vbus-typec disabled e GPIO35 `phoenix-usb-source-off` output LOW.
Nessun file di autorizzazione viene creato automaticamente. Il permesso scade
al reboot e `vbus_verified` resta false. Non prova la tensione al connettore,
né il comportamento del bootloader. Non riavviare con il cavo dati inserito.
La dipendenza BindsTo impedisce al worker di partire se il gadget fallisce;
per ripristinare il servizio senza USB, fermare il worker, ripristinare la
configurazione precedente e rimuovere il solo drop-in USB, quindi ricaricare
systemd e riavviare i servizi. Non modificare il firewall del Mac.

Phoenix può creare un gadget configfs con una sola funzione **CDC-ECM oppure
CDC-NCM**, quindi gestire DHCP sulla rete USB `192.168.7.0/24`. La rete usa le
stesse policy USB, NAT, port forwarding, blocco iniziale e WireGuard del backend
Linux. Il Wi-Fi STA può essere l'uplink in alternativa all'Ethernet; il servizio
USB non dipende dall'AP e resta distinto dal cambio AP/STA.

Sul banco ROCK 4C+ è stato verificato CDC-ECM su macOS con link high-speed
attraverso hub USB 2.0. Il VBUS non è stato misurato e NCM/SuperSpeed non sono
qualificati. Il descrittore è conservativo USB 2.0; non promette SuperSpeed.

## Separazione dei privilegi

`phoenix-usb-gadget.service` è un oneshot separato, opt-in. Crea solo
`/sys/kernel/config/usb_gadget/phoenix`, associa il controller **per ultimo** e
rimuove soltanto la propria configurazione. Non monta configfs, non carica
moduli, non scrive ruoli USB/regolatori e non adotta un gadget Radxa/ADB già
presente. Se la UDC è occupata o l'interfaccia esiste, l'avvio fallisce.
Il worker continua a non avere accesso in scrittura a configfs.

Il worker aggiunge indirizzo e DHCP solo dopo la barriera firewall. Rifiuta
interfacce gestite da NetworkManager, indirizzi IPv4 estranei e sovrapposizioni
con le route esistenti. Il servizio DHCP usa esclusivamente l'interfaccia USB;
non è un resolver DNS. Arresto/errore rimuovono l'indirizzo aggiunto da Phoenix.
La morte del DHCP o la rimozione del binding bloccano l'inoltro al successivo tick.
Un semplice scollegamento del cavo non richiede di ricreare il gadget.

## Preparazione sul target, quando disponibile

Non eseguire questa procedura sul Mac. Per la ROCK 4C+ resta aperta la verifica
fisica dei 5 V sulla USB-A OTG: **non collegare il cavo al Mac finché non è risolta**.
`vbus_verified` è una conferma dell'operatore dopo la verifica, non una misura
eseguita dal programma e non un comando per spegnere l'alimentazione.

1. Identificare modello, immagine/kernel, UDC e servizi USB presenti:
   `sudo /opt/phoenix/bin/phoenix usb-gadget inspect`.
   Un elenco UDC vuoto richiede prima la configurazione del kernel/ruolo periferica.
2. Verificare supporto configfs/libcomposite e della funzione scelta. Predisporre
   i moduli richiesti e il mount configfs con la procedura della distribuzione.
   L'osservazione storica del kernel Radxa b60 indicava ECM disponibile e NCM
   non selezionato: ricontrollare il kernel effettivamente installato.
3. Risolvere esplicitamente eventuali servizi gadget preesistenti, conservandone
   la configurazione. Phoenix non arresta né cancella automaticamente Radxa/ADB.
4. Assegnare una interfaccia USB dedicata, per esempio `phusb0`, anche in
   `interfaces.usb` di `/etc/phoenix/target.json`. Prima di crearla, renderla
   non gestita da NetworkManager con una configurazione persistente limitata
   **a quel nome**. Non disabilitare NetworkManager globalmente.
5. Aggiungere l'oggetto seguente con valori verificati sul target:

```json
"usb_gadget": {
  "enabled": true,
  "function": "ecm",
  "udc": "NOME_ESATTO_DA_SYS_CLASS_UDC",
  "serial": "IDENTIFICATIVO_UNIVOCO_STABILE",
  "vendor_id": "0xVVVV",
  "product_id": "0xPPPP",
  "vbus_verified": false,
  "dns": "103.86.96.100"
}
```

VID/PID sono segnaposto volutamente non validi: usare identificativi autorizzati
per il dispositivo/banco, non distribuire identificativi presi da altri prodotti.
Non è previsto fallback automatico NCM→ECM: scegliere la funzione supportata,
poi provarla con il Mac. I due MAC locali vengono derivati dal seriale, che deve
essere diverso per ogni dispositivo. Arrestare il gadget prima di modificare
funzione, identificativi o nome interfaccia.

6. L'installatore iniziale include l'unità nuova senza avviarla. Per una
   installazione esistente, installare sul target la copia revisionata di
   `platforms/linux/deploy/phoenix-usb-gadget.service` in `/etc/systemd/system/`.
   Aggiungere un drop-in di `phoenix-control.service`:

```ini
[Unit]
BindsTo=phoenix-usb-gadget.service
After=phoenix-usb-gadget.service
```

7. Solo dopo le verifiche elettriche, impostare `vbus_verified: true`, eseguire
   `systemctl daemon-reload`, arrestare il worker e riavviarlo: il drop-in fa
   partire il gadget prima del DHCP. Fermare il worker prima di rimuovere il
   drop-in o disabilitare USB. Nessuna di queste azioni è stata eseguita offline.

## Pannello diretto e prova con il Mac

Per l’installazione USB attuale aprire **http://192.168.7.1**, con redirect
HTTPS e login password. Vedere [USB_ADMIN.md](USB_ADMIN.md). Il tunnel SSH
sotto resta un’alternativa di manutenzione per deployment precedenti.


Dopo la connessione sicura del cavo, verificare che il Mac riceva un indirizzo
`192.168.7.20–200`, router `192.168.7.1`. Per il pannello resta il deployment
HTTPS via SSH, senza esporre automaticamente nuove porte web:

```sh
ssh -L 8443:127.0.0.1:8443 UTENTE_ROCK@192.168.7.1
```

Aprire `https://127.0.0.1:8443`, verificare il certificato come descritto nella
[guida deployment](README.md) e usare il proprio token amministrativo.
Selezionare l'uplink realmente collegato e connettere la VPN. All'avvio non si
naviga finché il traffico non è autorizzato: non c'è fallback diretto automatico.
Per provare davvero Phoenix, evitare che il Mac usi contemporaneamente un'altra
uscita Internet; nessuna preferenza o route del Mac viene modificata dal software.
Il cambio DNS aggiorna DHCP, ma un client con lease già acquisita può richiedere
rinnovo della lease o riconnessione USB prima di usare il nuovo DNS.

## Evidenze senza scheda

- Test con modello configfs: ECM/NCM, binding per ultimo, rollback, rifiuto di
  controller/configurazioni estranee e gate VBUS. **Non sono enumerazione USB.**
- Test unitari di ownership, DHCP, conflitti, cleanup e blocco su errore.
- `kernel_usb_dhcp_in_isolated_container` (`rust/src/lan.rs`, via
  `tools/rust-kernel-tests.sh`): lease reale con dnsmasq e `busybox udhcpc` su
  veth nel container; gateway/DNS, cambio DNS e cleanup.
- Test kernel esistente: regole nftables blocked/direct/vpn e route WireGuard
  dentro namespace isolato. Nessun account VPN reale o throughput misurato.

Riferimento implementativo: [Linux USB gadget configfs](https://docs.kernel.org/usb/gadget_configfs.html).
