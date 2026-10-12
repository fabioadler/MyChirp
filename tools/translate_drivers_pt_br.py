"""Extend pt_BR/ja_JP/zh_CN catalogs with driver-facing setting strings.

The UV-5R-family drivers expose settings with hard-coded English labels
(Carrier Squelch Level, VHF Lower Limit etc). We translate them here so
the Settings tab shows Portuguese (and others) instead of falling back
to English.
"""

import os
import polib

BASE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "mychirp", "locale"))


# Translations for the UV-5R/BOM-5701 driver setting labels (shortname).
# Sources: mychirp/drivers/uv5r.py + baofeng_common.py.
PT_BR = {
    # Basic Settings
    "Basic Settings": "Configurações básicas",
    "Carrier Squelch Level": "Nível de squelch (carrier)",
    "Battery Saver": "Economia de bateria",
    "Backlight Timeout": "Tempo de iluminação de fundo",
    "Beep": "Beep de teclas",
    "Timeout Timer": "Tempo limite de transmissão (TOT)",
    # Advanced Settings
    "Advanced Settings": "Configurações avançadas",
    "VOX Sensitivity": "Sensibilidade VOX",
    "Dual Watch": "Escuta dupla (dual watch)",
    "Dual Watch Channel": "Canal da escuta dupla",
    "Tuning Step": "Passo da frequência",
    "Voice Prompt": "Anúncio por voz",
    "Scrambler": "Scrambler",
    "Squelch Tail Elimination": "Eliminação de cauda (STE)",
    "Repeater Tone Tail": "Cauda de tom de repetidor",
    "Tone Repeat Timer": "Temporizador de repetição de tom",
    "Reset": "Reiniciar (reset)",
    "All Menus": "Todos os menus",
    "BCL": "BCL (Bloqueio de canal ocupado)",
    "PTT ID": "ID do PTT",
    "PTT ID Code": "Código do ID PTT",
    "Alarm Code": "Código de alarme",
    "Alarm Mode": "Modo de alarme",
    "Alarm Sound": "Som de alarme",
    "Squelch %i": "Squelch %i",
    "VHF Lower Limit (MHz)": "Limite mínimo VHF (MHz)",
    "VHF Upper Limit (MHz)": "Limite máximo VHF (MHz)",
    "UHF Lower Limit (MHz)": "Limite mínimo UHF (MHz)",
    "UHF Upper Limit (MHz)": "Limite máximo UHF (MHz)",
    "VHF TX Enabled": "TX VHF habilitado",
    "UHF TX Enabled": "TX UHF habilitado",
    # Other Settings
    "Other Settings": "Outras configurações",
    "Firmware Message 1": "Mensagem de firmware 1",
    "Firmware Message 2": "Mensagem de firmware 2",
    "6+Power-On Message 1": "Mensagem de energização 6+1",
    "6+Power-On Message 2": "Mensagem de energização 6+2",
    "Power-On Message": "Mensagem ao ligar",
    "Power-On Message 1": "Mensagem ao ligar 1",
    "Power-On Message 2": "Mensagem ao ligar 2",
    # Work Mode Settings
    "Work Mode Settings": "Configurações de modo de trabalho",
    "Display": "Exibição",
    "VFO/MR Mode": "Modo VFO/MR",
    "Keypad Lock": "Bloqueio do teclado",
    "MR A Channel": "Canal MR A",
    "MR B Channel": "Canal MR B",
    "VFO A Frequency": "Frequência VFO A",
    "VFO B Frequency": "Frequência VFO B",
    "VFO A Shift": "Shift VFO A",
    "VFO B Shift": "Shift VFO B",
    "VFO A Offset": "Offset VFO A",
    "VFO B Offset": "Offset VFO B",
    "VFO A Power": "Potência VFO A",
    "VFO B Power": "Potência VFO B",
    "VFO A Bandwidth": "Largura de banda VFO A",
    "VFO B Bandwidth": "Largura de banda VFO B",
    "VFO A PTT ID": "ID PTT VFO A",
    "VFO B PTT ID": "ID PTT VFO B",
    "VFO A Step": "Passo VFO A",
    "VFO B Step": "Passo VFO B",
    # DTMF
    "DTMF Settings": "Configurações DTMF",
    "ANI Code": "Código ANI",
    "ANI ID": "ID ANI",
    "DTMF Speed": "Velocidade DTMF",
    "DTMF Side Tone": "Tom lateral DTMF",
    "DTMF Separator Code": "Separador DTMF",
    "DTMF Group Code": "Código de grupo DTMF",
    "DTMF Decode Response": "Resposta decode DTMF",
    "PTT ID Code %i": "Código PTT ID %i",
    "DTMF PTT ID": "ID PTT DTMF",
    "Busy Lockout": "Bloqueio com canal ocupado",
    # Tone
    "Tone Mode": "Modo Tom",
    "Tone": "Tom",
    "ToneSql": "TomSql",
    "DTCS Code": "Código DTCS",
    "DTCS Rx Code": "Código DTCS Rx",
    "DTCS Tx Polarity": "Polaridade DTCS TX",
    "DTCS Rx Polarity": "Polaridade DTCS RX",
    "Duplex": "Duplex",
    "Offset": "Offset",
    "Mode": "Modo",
    "Skip": "Ignorar",
    "Power": "Potência",
    "Comment": "Comentário",
    "Name": "Nome",
    "Frequency": "Frequência",
    # Fetch source labels
    "Priority Channel": "Canal prioritário",
    "Scan Type": "Tipo de varredura",
    "Scan Resume": "Retomada de varredura",
    "Tone Burst": "Tom de burst",
    "Signal Strength Squelch": "Squelch por intensidade de sinal",
    "Squelch 1": "Squelch 1",
    "Squelch 2": "Squelch 2",
    "Squelch 3": "Squelch 3",
    "Squelch 4": "Squelch 4",
    "Squelch 5": "Squelch 5",
    "Squelch 6": "Squelch 6",
    "Squelch 7": "Squelch 7",
    "Squelch 8": "Squelch 8",
    "Squelch 9": "Squelch 9",
    "FM Radio": "Rádio FM",
    "FM Radio Preset": "Preset de rádio FM",
    "FM Radio Enable": "Rádio FM habilitado",
    "Service Settings": "Configurações de serviço",
    "DTMF Attack Time": "Tempo de ataque DTMF",
    "ANI Code %i": "Código ANI %i",
}


def add_to(po_path, translations):
    po = polib.pofile(po_path)
    existing = {e.msgid for e in po}
    added = updated = 0
    for en, tr in translations.items():
        e = [e for e in po if e.msgid == en]
        if e:
            if not e[0].msgstr or e[0].msgstr != tr:
                e[0].msgstr = tr
                updated += 1
        else:
            po.append(polib.POEntry(msgid=en, msgstr=tr))
            added += 1
    po.save(po_path)
    mo_dir = os.path.join(os.path.dirname(po_path),
                          os.path.basename(po_path).replace('.po', ''),
                          'LC_MESSAGES')
    os.makedirs(mo_dir, exist_ok=True)
    po.save_as_mofile(os.path.join(mo_dir, 'CHIRP.mo'))
    return added, updated


if __name__ == "__main__":
    for lang, trans in (('pt_BR', PT_BR),):
        a, u = add_to(os.path.join(BASE, '%s.po' % lang), trans)
        print('%s: +%i novas, %i atualizadas' % (lang, a, u))
