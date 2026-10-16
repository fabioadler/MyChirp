"""Protocolo de boot mode e acesso à flash principal da família UV-17Pro.

Implementação baseada na engenharia reversa do `Import Picture tools.exe`
v1.1 (CPS oficial Baofeng UV-5RM Plus / T6UV Series, 2023).

Protocolo:
1. Entra em modo clone normal (magic PROGRAMBFNORMALU + handshake)
2. Envia 0xA5 (CMD_HANDSHAKE) para entrar em boot/flash mode
3. Define endereço de flash (CMD_SETADDRESS)
4. Apaga setor (CMD_ERASE) / lê (CMD_READFLASH) / escreve (CMD_WRITEFLASH)
5. Finaliza com CMD_OVER

AVISO: gravação na flash principal pode causar BRICK PERMANENTE se os
dados estiverem errados. Sempre faça um dump completo antes de gravar.
"""
import logging
import struct
import time

LOG = logging.getLogger(__name__)

# Comandos (COMMAND_TYPE enum, extraído do .NET Constant table)
CMD_HANDSHAKE = 0xA5    # entra em boot mode
CMD_SETADDRESS = 0x02   # define endereço de flash
CMD_ERASE = 0x03        # apaga setor
CMD_WRITE = 0x57        # 'W' escreve bloco de 1024 bytes
CMD_OVER = 0x0C         # finaliza sessão
CMD_READ = 0x52         # 'R' lê bloco (mesmo do clone, mas flash mode)

# Endereços de flash (ADDR enum)
ADDR_FONT = 0x10000       # 64 KB
ADDR_IMAGE = 0xC0000      # 768 KB — UV17/18/19/20
ADDR_VOICE = 0xD0000      # 832 KB
ADDR_IMAGE_UV21 = 0x100000  # 1 MB — UV21

# Constantes
BLOCK_SIZE = 1024         # tamanho do bloco de dados
FLASH_TIMEOUT = 2.0       # timeout de resposta do rádio
CRC_POLY = 0x1021         # CRC-16-CCITT
CRC_INIT = 0x8000        # valor inicial do CRC


def crc16_ccitt(data, crc=CRC_INIT):
    """CRC-16-CCITT como usado pelo Import Picture tools (poly 0x1021)."""
    for byte in data:
        crc ^= (byte << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _rawsend(pipe, data):
    pipe.write(data)
    pipe.flush()


def _rawrecv(pipe, count, timeout=FLASH_TIMEOUT):
    """Lê @count bytes com timeout; retorna b'' se nada chegar."""
    data = b''
    deadline = time.monotonic() + timeout
    while len(data) < count and time.monotonic() < deadline:
        chunk = pipe.read(count - len(data))
        if chunk:
            data += chunk
    return data


def enter_clone_mode(pipe):
    """Passo 1: entra no modo clone normal (magic + handshake).

    Retorna True se o rádio respondeu com ACK 0x06.
    """
    _rawsend(pipe, b'PROGRAMBFNORMALU')
    ack = _rawrecv(pipe, 1)
    if ack != b'\x06':
        LOG.debug('Clone magic falhou: ack=%r', ack)
        return False
    # handshake do clone (0x46, 0x4D, SEND!)
    _rawsend(pipe, b'\x46')
    _rawrecv(pipe, 16)
    _rawsend(pipe, b'\x4d')
    _rawrecv(pipe, 15)
    _rawsend(pipe, b'\x53\x45\x4E\x44\x21\x05\x0D\x01\x01\x01\x04\x11'
                   b'\x08\x05\x0D\x0D\x01\x11\x0F\x09\x12\x09\x10\x04\x00')
    _rawrecv(pipe, 1)
    return True


def enter_boot_mode(pipe):
    """Passo 2: entra em boot/flash mode após o clone mode.

    Envia 0xA5 e espera resposta. Retorna True se o rádio entrou.
    """
    _rawsend(pipe, bytes([CMD_HANDSHAKE]))
    time.sleep(0.1)
    resp = _rawrecv(pipe, 16)
    LOG.debug('Boot mode response: %r', resp)
    # O rádio deve responder com algo (formato exato a confirmar em HW)
    return len(resp) > 0


def set_flash_address(pipe, address):
    """Define o endereço de flash para as próximas operações."""
    frame = bytes([CMD_SETADDRESS])
    frame += struct.pack('>I', address)
    _rawsend(pipe, frame)
    ack = _rawrecv(pipe, 1)
    return ack == b'\x06'


def read_flash_block(pipe, address, size=BLOCK_SIZE):
    """Lê um bloco da flash no endereço especificado."""
    # Frame: CMD_READ + addr (3 bytes BE) + size
    frame = bytes([CMD_READ])
    frame += struct.pack('>I', address)[1:]  # 3 bytes do endereço
    frame += bytes([size & 0xFF])  # tamanho (máximo 255 por frame?)
    # NOTA: o Import Picture tools usa blocos de 1024; o formato exato
    # do frame de leitura precisa ser confirmado em hardware
    _rawsend(pipe, frame)
    data = _rawrecv(pipe, size + 4)  # +4 header
    if len(data) >= 4:
        return data[4:]
    return b''


def write_flash_block(pipe, address, data):
    """Escreve um bloco de dados na flash (máximo 1024 bytes).

    Formato do frame (inferido do IL):
    [0xA5] [FF FF FF FF FF] [data 1024 bytes] [CRC16 lo hi]
    """
    if len(data) > BLOCK_SIZE:
        raise ValueError('Bloco maior que %d bytes' % BLOCK_SIZE)
    # Padding com 0xFF
    data = data.ljust(BLOCK_SIZE, b'\xFF')
    # Header + dados + CRC
    crc = crc16_ccitt(data)
    frame = bytes([CMD_WRITE])
    frame += struct.pack('>I', address)
    frame += data
    frame += struct.pack('<H', crc)
    _rawsend(pipe, frame)
    ack = _rawrecv(pipe, 1)
    return ack == b'\x06'


def erase_flash_sector(pipe, address):
    """Apaga o setor de flash que contém o endereço."""
    frame = bytes([CMD_ERASE])
    frame += struct.pack('>I', address)
    _rawsend(pipe, frame)
    # Apagar leva mais tempo
    ack = _rawrecv(pipe, 1, timeout=5.0)
    return ack == b'\x06'


def end_boot_mode(pipe):
    """Finaliza a sessão de boot mode."""
    _rawsend(pipe, bytes([CMD_OVER]))
    time.sleep(0.2)
    _rawrecv(pipe, 16)


def read_boot_image_from_radio(pipe, image_addr=ADDR_IMAGE,
                               total_size=BLOCK_SIZE * 100):
    """Lê a boot image atual da flash do rádio.

    Retorna os bytes crus da imagem ou None se falhar.
    """
    if not enter_clone_mode(pipe):
        LOG.error('Clone mode falhou')
        return None
    time.sleep(0.5)
    if not enter_boot_mode(pipe):
        LOG.error('Boot mode falhou')
        return None
    time.sleep(0.5)

    result = b''
    for offset in range(0, total_size, BLOCK_SIZE):
        addr = image_addr + offset
        data = read_flash_block(pipe, addr)
        if not data:
            LOG.warning('Flash read falhou em 0x%X', addr)
            break
        result += data
        LOG.debug('Flash 0x%X: %d bytes lidos', addr, len(data))

    end_boot_mode(pipe)
    return result


def upload_boot_image(pipe, bmp_data, image_addr=ADDR_IMAGE):
    """Faz upload de uma boot image para a flash do rádio.

    AVISO: pode causar BRICK se os dados estiverem errados!
    Sempre faça um dump antes (read_boot_image_from_radio).
    """
    if not enter_clone_mode(pipe):
        LOG.error('Clone mode falhou')
        return False
    time.sleep(0.5)
    if not enter_boot_mode(pipe):
        LOG.error('Boot mode falhou')
        return False
    time.sleep(0.5)

    # Define o endereço
    if not set_flash_address(pipe, image_addr):
        LOG.error('SetAddress falhou em 0x%X', image_addr)
        return False

    # Apaga o setor
    if not erase_flash_sector(pipe, image_addr):
        LOG.error('Erase falhou em 0x%X', image_addr)
        return False

    # Envia em blocos de 1024
    blocks = [bmp_data[i:i + BLOCK_SIZE]
              for i in range(0, len(bmp_data), BLOCK_SIZE)]
    for i, block in enumerate(blocks):
        addr = image_addr + (i * BLOCK_SIZE)
        if not write_flash_block(pipe, addr, block):
            LOG.error('Write falhou em 0x%X (bloco %d/%d)',
                      addr, i + 1, len(blocks))
            return False
        LOG.debug('Flash 0x%X: bloco %d/%d OK', addr, i + 1, len(blocks))

    end_boot_mode(pipe)
    return True
