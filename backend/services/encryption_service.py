"""
Servicio de cifrado simétrico con Fernet (cryptography).

Uso:
    from services.encryption_service import EncryptionService

    cifrado   = EncryptionService.encrypt("mi_api_key_secreta")
    original  = EncryptionService.decrypt(cifrado)

La clave Fernet se lee de la variable de entorno FERNET_SECRET_KEY.
Si no existe, se genera una aleatoria IN-MEMORY y se imprime un aviso:
los datos cifrados NO sobrevivirán reinicios en ese caso, así que siempre
define la variable en producción.

Cómo generar una clave válida:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_ENV_VAR = "FERNET_SECRET_KEY"

def _load_or_generate_key() -> bytes:
    """Carga la clave desde la variable de entorno o genera una temporal."""
    raw = os.getenv(_ENV_VAR, "").strip()
    if raw:
        return raw.encode()

    # Fallback: clave temporal (sólo para desarrollo sin .env configurado)
    generated = Fernet.generate_key()
    logger.warning(
        "FERNET_SECRET_KEY no esta definida. Se ha generado una clave "
        "temporal en memoria. Los datos cifrados NO seran recuperables tras "
        "reiniciar el servidor. Define la variable de entorno para produccion."
    )
    return generated


_fernet = Fernet(_load_or_generate_key())


class EncryptionService:
    """Cifrado/descifrado simetrico Fernet para datos sensibles (API keys, tokens...)."""

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """
        Cifra un texto plano y devuelve el token Fernet como string.
        Lanza ValueError si plaintext es None o vacio.
        """
        if not plaintext:
            raise ValueError("El texto a cifrar no puede estar vacio.")
        token_bytes = _fernet.encrypt(plaintext.encode("utf-8"))
        return token_bytes.decode("utf-8")

    @staticmethod
    def decrypt(token: str) -> str:
        """
        Descifra un token Fernet y devuelve el texto original.
        Lanza ValueError si el token es invalido o ha sido manipulado.
        """
        if not token:
            raise ValueError("El token a descifrar no puede estar vacio.")
        try:
            plaintext_bytes = _fernet.decrypt(token.encode("utf-8"))
            return plaintext_bytes.decode("utf-8")
        except InvalidToken as e:
            raise ValueError(
                "No se pudo descifrar el token: puede que la clave Fernet haya "
                "cambiado o que el valor este corrupto."
            ) from e

    @staticmethod
    def is_fernet_token(value: str) -> bool:
        """
        Heuristica rapida para saber si un valor ya esta cifrado con Fernet.
        Los tokens Fernet son base64url y empiezan siempre con 'gAAA'.
        Util para migrar datos existentes sin volver a cifrar los que ya lo estan.
        """
        return isinstance(value, str) and value.startswith("gAAA")
