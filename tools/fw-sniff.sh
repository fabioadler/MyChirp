#!/bin/bash
# fw-sniff.sh — bridge com sniffing para capturar o trafego da CPS oficial
# sob wine sem tocar nos binarios:  [wine exe] <-> pty <-sniff-> /dev/ttyUSB?
#                                   (side B)                (side B real)
#
# Uso:
#   tools/fw-sniff.sh /dev/ttyUSB0 "drive_c/cps_uv5r/BF_5R_ThreeBand.exe" [args...]
#
# Saida: tools/cps/cap/console.txt (hex anotado por lado) + A.bin/B.bin (raw)
# Depois: tools/sniff_analyze.py tools/cps/cap/console.txt
set -u

REAL="${1:?pass device real (ex: /dev/ttyUSB0)}"
EXE="${2:?pass exe da CPS (caminho wine)}"
shift 2

CPS_CAP=tools/cps/cap
mkdir -p "$CPS_CAP"

SNIFF=/tmp/opencode/serialsniff
if [ ! -x "$SNIFF" ]; then
    gcc -O2 -std=gnu89 -D_DEFAULT_SOURCE -o "$SNIFF" tools/serialsniff.c || exit 1
fi

rm -f "$CPS_CAP"/console.txt "$CPS_CAP"/A.bin "$CPS_CAP"/B.bin

"$SNIFF" -A pty --logA "$CPS_CAP/A.bin" \
         -B "$REAL" --logB "$CPS_CAP/B.bin" -d 32 2>&1 \
  > >(tee "$CPS_CAP/console.txt") &
SNIFF_PID=$!

# espera o sniffer imprimir o caminho do pty como lado A
PTY=""
for _ in $(seq 1 40); do
    PTY=$(grep -aoE '^/dev/pts/[0-9]+' $CPS_CAP/console.txt | head -1)
    [ -n "$PTY" ] && break
    sleep 0.25
done
if [ -z "$PTY" ]; then
    echo "ERRO: pty do sniffer nao apareceu" >&2
    kill $SNIFF_PID 2>/dev/null; exit 1
fi
echo "== sniffer ativo: lado A=$PTY (wine)  lado B=$REAL (radio)" >&2

# COM1 do wine → o pty do sniffer (a CPS escolhe COM1 na UI)
WINE_DOCDIR="${WINEPREFIX:-$HOME/.wine}/dosdevices"
ln -sf "$PTY" "$WINE_DOCDIR/com1"

cleanup() {
    kill $SNIFF_PID 2>/dev/null
    wait $SNIFF_PID 2>/dev/null
}
trap cleanup EXIT

echo "== executandowine: $EXE $*" >&2
WINEDEBUG=-all wine "$EXE" "$@"
status=$?
echo "== wine saiu (rc=$status)" >&2
echo "== capturas: $CPS_CAP/{console.txt,A.bin,B.bin}" >&2
exit $status
