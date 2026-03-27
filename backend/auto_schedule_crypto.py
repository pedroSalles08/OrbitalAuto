from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from auto_scheduler import AutoScheduleConfigError


class AutoScheduleCredentialCipher:
    def __init__(self, key: str) -> None:
        normalized_key = (key or "").strip()
        if not normalized_key:
            raise AutoScheduleConfigError(
                "AUTO_SCHEDULE_ENCRYPTION_KEY is not configured."
            )

        try:
            self._fernet = Fernet(normalized_key.encode("utf-8"))
        except Exception as exc:
            raise AutoScheduleConfigError(
                "AUTO_SCHEDULE_ENCRYPTION_KEY is invalid."
            ) from exc

    def encrypt(self, password: str) -> str:
        secret = (password or "").strip()
        if not secret:
            raise AutoScheduleConfigError(
                "Senha do Orbital obrigatoria para salvar a automacao."
            )
        return self._fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_password: str) -> str:
        token = (encrypted_password or "").strip()
        if not token:
            raise AutoScheduleConfigError(
                "Auto schedule credentials are not configured."
            )

        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise AutoScheduleConfigError(
                "Stored auto schedule credentials could not be decrypted."
            ) from exc
