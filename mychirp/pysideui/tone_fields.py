"""Lógica de campos de tom (CTCSS/DCS) por Tone Mode.

Compartilhada entre o grid de memórias (tabs/memories.py) e o dialog de
edição de canal (dialogs/memory_edit.py):

- os campos de tom só são editáveis quando pertencem ao tmode atual
  (o usuário escolhe o tipo primeiro);
- ao trocar o tipo, os campos dos outros tipos são limpos (voltam aos
  defaults) e bloqueados; com tmode vazio, todos ficam bloqueados e
  vazios.
"""

TONE_FIELDS = ("rtone", "ctone", "dtcs")

# Defaults do chirp_common.Memory: sem tom configurado, os campos
# carregam estes valores (renderizados em branco quando não usados).
TONE_DEFAULTS = {
    "rtone": 88.5,
    "ctone": 88.5,
    "dtcs": 23,
}


def used_tone_columns_for(tmode, cross_mode=""):
    """Campos de tom relevantes para @tmode ("" -> nenhum)."""
    if tmode == "Tone":
        return {"rtone"}
    if tmode == "TSQL":
        return {"rtone", "ctone"}
    if tmode == "DTCS":
        return {"dtcs"}
    if tmode == "Cross":
        tx, _, rx = (cross_mode or "").partition("->")
        used = set()
        if tx == "Tone":
            used.add("rtone")
        elif tx == "DTCS":
            used.add("dtcs")
        if rx == "Tone":
            used.add("ctone")
        elif rx == "DTCS":
            used.add("dtcs")
        return used
    return set()


def used_tone_columns(mem):
    """Campos de tom relevantes para o tmode atual de @mem."""
    return used_tone_columns_for(mem.tmode,
                                 getattr(mem, "cross_mode", "") or "")


def clear_unused_tones(mem, tmode):
    """Zera (defaults) os campos de tom que não pertencem a @tmode.

    Usado ao trocar o Tone Mode: os campos do tipo anterior são limpos
    para os defaults; com tmode vazio todos são limpos.
    """
    used = used_tone_columns_for(tmode,
                                 getattr(mem, "cross_mode", "") or "")
    for field, default in TONE_DEFAULTS.items():
        if field not in used:
            setattr(mem, field, default)
    return used
