import base64
import binascii
import json
import os
import re
from typing import Any

key_bytes = os.urandom(64)


def encrypt(input_string: str):
    input_bytes = input_string.encode()
    result = xor(input_bytes)
    return base64.urlsafe_b64encode(result).decode().rstrip('=')


def decrypt(input_string: str):
    padding_needed = (-len(input_string)) % 4
    if padding_needed:
        input_string += "=" * padding_needed
    if not re.fullmatch(r"[A-Za-z0-9_-]+=?=?", input_string):
        raise ValueError("Invalid encrypted payload")
    try:
        input_bytes = base64.urlsafe_b64decode(input_string)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid encrypted payload") from exc
    result = xor(input_bytes)
    try:
        return result.decode()
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid encrypted payload") from exc


def xor(input_bytes):
    return bytes([input_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(input_bytes))])


def urlsafe_base64(input_string: str) -> str:
    input_bytes = input_string.encode("utf-8")
    base64_bytes = base64.urlsafe_b64encode(input_bytes)
    base64_string = base64_bytes.decode("utf-8")
    return base64_string


def urlsafe_base64_decode(base64_string: str) -> str:
    padding = '=' * (-len(base64_string) % 4)
    base64_string_padded = base64_string + padding
    base64_bytes = base64_string_padded.encode("utf-8")
    decoded_bytes = base64.urlsafe_b64decode(base64_bytes)
    return decoded_bytes.decode("utf-8")


def extract_and_decode_var(var_name: str, response: str) -> str:
    pattern = rf'var\s+{re.escape(var_name)}\s*=\s*atob\("([^"]+)"\);'
    matches = re.findall(pattern, response)
    if not matches:
        raise ValueError(f"Variable '{var_name}' not found in response")
    b64 = matches[-1]
    return base64.b64decode(b64).decode("utf-8")


def decode_bundle(response_text: str) -> dict[str, Any]:
    def normalize(data: dict[str, Any]) -> dict[str, Any]:
        decoded: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    pad = "=" * (-len(value) % 4)
                    decoded[key] = base64.b64decode(value + pad).decode("utf-8")
                except Exception:
                    decoded[key] = value
            else:
                decoded[key] = value
        return decoded

    def parse_candidate(candidate: str) -> dict[str, Any] | None:
        try:
            decoded_candidate = base64.b64decode(candidate + "=" * (-len(candidate) % 4)).decode(
                "utf-8"
            )
        except Exception:
            return None
        try:
            data = json.loads(decoded_candidate)
        except json.JSONDecodeError:
            return None
        if any(key in data for key in ("b_ts", "b_sig", "b_host", "b_rnd")):
            return normalize(data)
        return None

    candidates = {response_text.strip()}
    candidates.update(
        re.findall(
            r'JSON\.parse\s*\(\s*atob\s*\(\s*["\']([^"\']{40,})["\']\s*\)\s*\)',
            response_text,
        )
    )
    candidates.update(
        re.findall(r'atob\s*\(\s*["\'](eyJ[A-Za-z0-9+/=]{40,})["\']\s*\)', response_text)
    )
    candidates.update(
        re.findall(
            r'(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*["\'](eyJ[A-Za-z0-9+/=]{40,})["\']',
            response_text,
        )
    )
    candidates.update(re.findall(r'["\'](eyJ[A-Za-z0-9+/=]{40,})["\']', response_text))
    candidates.update(re.findall(r'["\']([A-Za-z0-9+/=]{80,})["\']', response_text))

    for candidate in candidates:
        decoded = parse_candidate(candidate)
        if decoded:
            return decoded
    return {}
