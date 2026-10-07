import base64
import hashlib
import os
import urllib.parse
from io import StringIO
from typing import Optional

from onevizion import LogLevel, ModuleLog, Trackor
from paramiko import (
    AutoAddPolicy,
    ECDSAKey,
    Ed25519Key,
    PasswordRequiredException,
    PKey,
    RSAKey,
    SFTPClient,
    SSHClient,
)


class SFTPFileService:
    def __init__(self, sftp: SFTPClient) -> None:
        self._sftp = sftp

    def _build_path(self, base: str, file_name: str) -> str:
        return f"{base}/{file_name}".replace("//", "/")

    def upload_file(self, file_path: str, directory: str, file_name: str) -> None:
        try:
            self._sftp.put(file_path, self._build_path(directory, file_name))
        except Exception as exception:
            raise ModuleError(
                f"Failed to upload file [{file_name}] to SFTP directory [{directory}]",
                exception,
            ) from exception

    def delete_file(self, directory: str, file_name: str) -> None:
        try:
            self._sftp.remove(self._build_path(directory, file_name))
        except FileNotFoundError:
            pass
        except Exception as exception:
            raise ModuleError(
                f"Failed to delete file [{file_name}] from SFTP directory [{directory}]",
                exception,
            ) from exception


class SFTPConnection:
    def __init__(self, ssh: SSHClient, sftp: SFTPClient) -> None:
        self._ssh = ssh
        self._sftp = sftp

    def __enter__(self) -> SFTPClient:
        return self._sftp

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._sftp.close()
        self._ssh.close()


class SFTPConnectionService:
    DEFAULT_PORT = 22
    FINGERPRINT_PADDING_SYMBOL = "="

    def __init__(self, settings_data: dict) -> None:
        self._url = settings_data["sftpUrl"]
        self._port = settings_data.get("sftpPort", SFTPConnectionService.DEFAULT_PORT)
        self._username = settings_data["sftpUserName"]
        self._password = settings_data.get("sftpPassword")
        self._private_key = settings_data.get("sftpPrivateKey")
        self._private_key_passphrase = settings_data.get("sftpPrivateKeyPassphrase")
        self._fingerprint = settings_data.get("sftpFingerprint")

    def _load_private_key(self, private_key: str, passphrase: Optional[str]) -> PKey:
        for key_class in (RSAKey, ECDSAKey, Ed25519Key):
            try:
                return key_class.from_private_key(
                    StringIO(private_key), password=passphrase
                )
            except PasswordRequiredException as exception:
                raise ModuleError(
                    "SFTP private key is protected with a passphrase",
                    "Fill in sftpPrivateKeyPassphrase in the settings file",
                ) from exception
            except Exception:
                continue
        raise ModuleError(
            "Failed to read SFTP private key",
            "Supported key types: RSA, ECDSA, Ed25519. Check sftpPrivateKey and sftpPrivateKeyPassphrase in the settings file",
        )

    def _create_ssh_connection(self, private_key: Optional[PKey]) -> SSHClient:
        connection_args = {
            "hostname": self._url,
            "port": self._port,
            "username": self._username,
        }

        if private_key:
            connection_args["pkey"] = private_key
        else:
            connection_args["password"] = self._password

        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        try:
            ssh.connect(**connection_args)
        except Exception:
            ssh.close()
            raise
        return ssh

    def connect(self) -> SFTPConnection:
        try:
            private_key = None

            if self._private_key:
                private_key = self._load_private_key(
                    self._private_key, self._private_key_passphrase
                )

            ssh = self._create_ssh_connection(private_key)
            try:
                self._compare_fingerprints(ssh)
                sftp = ssh.open_sftp()
            except Exception:
                ssh.close()
                raise
            return SFTPConnection(ssh, sftp)
        except ModuleError:
            raise
        except Exception as exception:
            raise ModuleError(
                f"Failed to connect to SFTP [{self._url}:{self._port}] as [{self._username}]",
                exception,
            ) from exception

    def _compare_fingerprints(self, ssh: SSHClient) -> None:
        if (
            self._fingerprint is not None
            and self._get_remote_server_fingerprint(ssh) != self._fingerprint
        ):
            raise ModuleError(
                "Fingerprint mismatch, the connection will be closed", None
            )

    def _get_remote_server_fingerprint(self, ssh: SSHClient) -> str:
        server_key_bytes = ssh.get_transport().get_remote_server_key().asbytes()
        sha256_digest = hashlib.sha256(server_key_bytes).digest()
        fingerprint = base64.b64encode(sha256_digest).decode("utf-8")
        return fingerprint.rstrip(self.FINGERPRINT_PADDING_SYMBOL)


class ModuleError(Exception):
    def __init__(self, error_message: str, description) -> None:
        super().__init__(
            error_message if description is None else f"{error_message}. {description}"
        )
        self._message = error_message
        self._description = description

    @property
    def message(self) -> str:
        return self._message

    @property
    def description(self) -> str:
        return self._description


class Module:
    DOWNLOADED_FILES_FOLDER = "downloaded_files"

    def __init__(
        self, ov_module_log: ModuleLog, ov_url: str, settings_data: dict
    ) -> None:
        self._module_log = ov_module_log
        self._sftp_connection_service = SFTPConnectionService(settings_data)
        self._trackor_service = TrackorService(ov_url, settings_data)
        self._directory = settings_data["sftpDirectory"]

    def start(self) -> None:
        self._module_log.add(LogLevel.INFO, "Starting Module")

        with self._sftp_connection_service.connect() as sftp:
            sftp_file_service = SFTPFileService(sftp)
            trackors = self._trackor_service.get_trackors_to_send()
            self._module_log.add(
                LogLevel.INFO, f"[{len(trackors)}] files found to send to SFTP"
            )
            failed_files_count = self._send_files(sftp_file_service, trackors)

        if failed_files_count > 0:
            raise ModuleError(
                f"[{failed_files_count}] of [{len(trackors)}] files have not been sent to SFTP",
                "See the previous errors for details. These files will be sent again on the next run",
            )

        self._module_log.add(LogLevel.INFO, "Module has been completed")

    def _send_files(self, sftp_file_service: SFTPFileService, trackors: list) -> int:
        failed_files_count = 0
        for trackor in trackors:
            trackor_key = trackor[TrackorService.TRACKOR_KEY_FIELD_NAME]
            try:
                self._send_file(sftp_file_service, trackor)
            except ModuleError as module_error:
                failed_files_count += 1
                self._module_log.add(
                    LogLevel.ERROR,
                    f"Trackor [{trackor_key}]: {module_error.message}",
                    str(module_error.description),
                )

        return failed_files_count

    def _send_file(self, sftp_file_service: SFTPFileService, trackor: dict) -> None:
        trackor_id = trackor[TrackorService.TRACKOR_ID_FIELD_NAME]
        trackor_key = trackor[TrackorService.TRACKOR_KEY_FIELD_NAME]
        file_path = None
        try:
            file_path = self._trackor_service.download_file(
                trackor_id, self.DOWNLOADED_FILES_FOLDER
            )
            file_name = urllib.parse.unquote(os.path.basename(file_path))
            self._module_log.add(
                LogLevel.DEBUG,
                f"File [{file_name}] for Trackor [{trackor_key}] has been downloaded",
            )

            sftp_file_service.delete_file(self._directory, file_name)
            sftp_file_service.upload_file(file_path, self._directory, file_name)
            self._trackor_service.clear_checkbox(trackor_id)
            self._module_log.add(
                LogLevel.INFO,
                f"File [{file_name}] for Trackor [{trackor_key}] has been sent to SFTP",
            )
        finally:
            if file_path:
                self._remove_file(file_path)

    def create_downloaded_files_folder(self) -> None:
        if not os.path.exists(Module.DOWNLOADED_FILES_FOLDER):
            os.makedirs(Module.DOWNLOADED_FILES_FOLDER)

    def remove_downloaded_files(self) -> None:
        for file_name in os.listdir(Module.DOWNLOADED_FILES_FOLDER):
            self._remove_file(f"{self.DOWNLOADED_FILES_FOLDER}/{file_name}")

    def _remove_file(self, file_path: str) -> None:
        try:
            os.remove(file_path)
            self._module_log.add(LogLevel.DEBUG, f"File [{file_path}] has been deleted")
        except FileNotFoundError as exception:
            self._module_log.add(
                LogLevel.DEBUG,
                f"File [{file_path}] was not found for deletion. It may have already been deleted. Details: [{exception}]",
            )
        except Exception as exception:
            raise ModuleError(
                f"Failed to delete local file [{file_path}]", exception
            ) from exception


class TrackorService:
    TRACKOR_ID_FIELD_NAME = "TRACKOR_ID"
    TRACKOR_KEY_FIELD_NAME = "TRACKOR_KEY"
    TRACKORS_PER_RUN = 1000

    def __init__(self, ov_url: str, settings_data: dict) -> None:
        self._ov_url = ov_url
        self._ov_access_key = settings_data["ovAccessKey"]
        self._ov_secret_key = settings_data["ovSecretKey"]
        self._trackor_type = settings_data["ovTrackorType"]
        self._checkbox_field_name = settings_data["ovCheckboxFieldName"]
        self._efile_field_name = settings_data["ovEfileFieldName"]

    def _create_trackor(self) -> Trackor:
        return Trackor(
            trackorType=self._trackor_type,
            URL=self._ov_url,
            userName=self._ov_access_key,
            password=self._ov_secret_key,
            isTokenAuth=True,
        )

    def get_trackors_to_send(self) -> list:
        ov_trackor_type = self._create_trackor()
        ov_trackor_type.read(
            filters={self._checkbox_field_name: 1},
            fields=[TrackorService.TRACKOR_KEY_FIELD_NAME, self._checkbox_field_name],
            sort={TrackorService.TRACKOR_KEY_FIELD_NAME: "ASC"},
            page=1,
            perPage=TrackorService.TRACKORS_PER_RUN,
        )

        if len(ov_trackor_type.errors) != 0:
            raise ModuleError(
                f"Failed to get [{self._trackor_type}] Trackors with checked [{self._checkbox_field_name}]",
                ov_trackor_type.errors,
            )

        return ov_trackor_type.jsonData

    def download_file(self, trackor_id: int, folder: str) -> str:
        ov_trackor_type = self._create_trackor()
        file_name = ov_trackor_type.GetFile(
            trackorId=trackor_id, fieldName=self._efile_field_name
        )

        file_path = None
        if file_name and os.path.exists(file_name):
            file_path = os.path.join(folder, os.path.basename(file_name))
            os.replace(file_name, file_path)

        if len(ov_trackor_type.errors) != 0 or file_path is None:
            if file_path:
                os.remove(file_path)
            raise ModuleError(
                f"Failed to download file from [{self._efile_field_name}] for Trackor ID [{trackor_id}]",
                ov_trackor_type.errors,
            )

        return file_path

    def clear_checkbox(self, trackor_id: int) -> None:
        ov_trackor_type = self._create_trackor()
        ov_trackor_type.update(
            filters={TrackorService.TRACKOR_ID_FIELD_NAME: trackor_id},
            fields={self._checkbox_field_name: 0},
        )

        if len(ov_trackor_type.errors) != 0:
            raise ModuleError(
                f"File has been sent to SFTP, but failed to clear [{self._checkbox_field_name}] for Trackor ID [{trackor_id}]",
                ov_trackor_type.errors,
            )
