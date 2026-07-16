import json
import struct
from typing import BinaryIO


MAX_MESSAGE_BYTES = 1_048_576
NATIVE_PROTOCOL_VERSION = 2


def read_message(stream: BinaryIO) -> dict | None:
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("Native Messaging 消息头不完整")
    length = struct.unpack("<I", header)[0]
    if length > MAX_MESSAGE_BYTES:
        raise ValueError("Native Messaging 消息过大")
    payload = stream.read(length)
    if len(payload) != length:
        raise ValueError("Native Messaging 消息体不完整")
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("Native Messaging 消息必须是对象")
    return message


def write_message(stream: BinaryIO, message: dict) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("Native Messaging 响应过大")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()
