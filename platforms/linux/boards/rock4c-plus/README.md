# Primo avvio ROCK 4C+

Scelta iniziale verificata documentalmente il 2026-11-11:
**Radxa OS / Debian 12 Bookworm, immagine ROCK 4C+ KDE R2**, ARM64.

Fonti ufficiali:
- https://docs.radxa.com/en/rock4/rock4c%2B/download
- https://github.com/radxa-build/rock-4c-plus/releases

Usare l'immagine standard per ROCK 4C+, non una ISO Debian generica,
non l'immagine ROCK 4C senza Plus, non UFS e non una prerelease.
Controllare il checksum SHA-512 pubblicato per il file effettivamente scaricato.
Non è ancora stato scaricato o provato un sistema su questa scheda.

KDE è incluso nell'immagine supportata dal produttore. Dopo avere verificato
SSH e accesso di recupero, possiamo configurare l'avvio headless e aggiornare
i pacchetti. Non occorre un desktop per Phoenix. Il port non dipenderà da KDE.

## Preparazione

1. Scrivere l'immagine sulla microSD identificata (cancella il suo contenuto).
2. Inserire la microSD, collegare Ethernet al router e alimentazione 5V/3A.
3. Identificare l'IP e configurare accesso SSH e credenziali personali.
4. Installare sul ROCK i requisiti, non sul Mac:

   `sudo apt update && sudo apt install python3 iproute2 nftables wireguard-tools iw hostapd dnsmasq-base network-manager openssl curl conntrack ca-certificates`

   Prima dell'installazione inventariare NetworkManager e i servizi di rete
   esistenti: l'installazione di pacchetti può avviare servizi. Nessuna
   configurazione AP/DHCP/firewall va applicata prima di assegnare le interfacce.

5. Dal checkout sulla ROCK, eseguire l'inventario non distruttivo:

   `PYTHONPATH=platforms/linux/service python3 -m phoenix_linux.preflight`

Exit 2 indica requisiti mancanti/errore, exit 0 solo inventario completato.
Non certifica WireGuard, USB gadget, AP Wi-Fi o throughput. Nomi delle
interfacce, supporto kernel e modalità USB vanno rilevati sul dispositivo.

## Criteri del banco

Prima Wi-Fi client → gateway → Ethernet; poi VPN e test di blocco traffico.
USB device è una verifica indipendente, non un requisito già dimostrato.
Registrare immagine, checksum, kernel, link Ethernet, driver Wi-Fi e temperature
prima di associare una misura di prestazione a questa piattaforma.
