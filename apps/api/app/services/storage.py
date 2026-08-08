"""对象存储抽象(Phase 5):本地盘 / S3 兼容双模式。

- local(默认):写 data/images,经 FastAPI StaticFiles(/api/img)服务。
- s3:置 STORAGE_BACKEND=s3 + S3_* 凭据,上传到 S3/MinIO/OSS,返回公共 URL。
image_service 通过 save() 写图,DB 里 local_path 存返回的可访问路径。
"""

from typing import Optional

from app.config import settings


class StorageBackend:
    """统一存储接口。key 形如 "{storyboard_version_id}/shot_1.png"。"""

    async def save(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    async def delete_by_web_path(self, web_path: str) -> None:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """本地磁盘 + StaticFiles。web_path = /api/img/{key}。"""

    async def save(self, key: str, data: bytes) -> str:
        path = settings.images_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"/api/img/{key}"

    async def delete_by_web_path(self, web_path: str) -> None:
        prefix = "/api/img/"
        if not web_path or not web_path.startswith(prefix):
            return
        key = web_path[len(prefix):]
        path = settings.images_dir / key
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


class S3Storage(StorageBackend):
    """S3 兼容存储。web_path = {public_base}/{key}。

    参数化:可同时服务图片(走 settings.s3_*)与 TTS 音频(走 settings.tos_*)。
    aioboto3 懒加载:开发默认 local 时无需安装 aioboto3。
    """

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
        public_base: str,
        addressing_style: str = "auto",
        acl: Optional[str] = None,
    ) -> None:
        # endpoint 缺协议头时补 https://(aiobotocore 要求带 scheme;
        # 常见配置如 TOS_ENDPOINT=tos-cn-beijing.volces.com 直接写裸域名)。
        if endpoint and not (endpoint.startswith("http://") or endpoint.startswith("https://")):
            endpoint = "https://" + endpoint
        self.endpoint = endpoint or None
        self.bucket = bucket
        self.access_key = access_key or None
        self.secret_key = secret_key or None
        self.region = region or None
        self.public_base = public_base.rstrip("/") if public_base else ""
        # 火山 TOS 强制 virtual-hosted-style;acl=public-read 让对象可被 ATA/前端匿名拉取。
        self.addressing_style = addressing_style
        self.acl = acl

    async def _client(self):
        import aioboto3  # 懒加载
        from botocore.client import Config

        session = aioboto3.Session()
        return session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                s3={"addressing_style": self.addressing_style},
                signature_version="s3v4",
            ),
        )

    def _key_from_web_path(self, web_path: str) -> Optional[str]:
        if web_path and self.public_base and web_path.startswith(self.public_base + "/"):
            return web_path[len(self.public_base) + 1:]
        return None

    async def save(self, key: str, data: bytes) -> str:
        async with await self._client() as client:
            kwargs = {"Bucket": self.bucket, "Key": key, "Body": data}
            if self.acl:
                kwargs["ACL"] = self.acl
            await client.put_object(**kwargs)
        return f"{self.public_base}/{key}"

    async def delete_by_web_path(self, web_path: str) -> None:
        key = self._key_from_web_path(web_path)
        if not key:
            return
        async with await self._client() as client:
            await client.delete_object(Bucket=self.bucket, Key=key)


_backend: Optional[StorageBackend] = None
_audio_backend: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        if settings.storage_backend == "s3" and settings.s3_bucket:
            _backend = S3Storage(
                endpoint=settings.s3_endpoint,
                bucket=settings.s3_bucket,
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
                region=settings.s3_region,
                public_base=settings.s3_public_base,
            )
        else:
            _backend = LocalStorage()
    return _backend


def get_audio_storage() -> StorageBackend:
    """TTS 音频专用存储:始终走火山 TOS(S3 兼容)。

    ATA 需公网 URL 拉取音频,本地盘不可达;故音频独立于图片存储。
    未配 TOS_BUCKET 时仍返回实例,真正调用时报清晰错误。
    """
    global _audio_backend
    if _audio_backend is None:
        _audio_backend = S3Storage(
            endpoint=settings.tos_endpoint,
            bucket=settings.tos_bucket,
            access_key=settings.tos_access_key,
            secret_key=settings.tos_secret_key,
            region=settings.tos_region,
            public_base=settings.tos_public_base,
            addressing_style="virtual",
            acl="public-read",
        )
    return _audio_backend


async def save(key: str, data: bytes) -> str:
    return await get_storage().save(key, data)


async def delete_by_web_path(web_path: str) -> None:
    await get_storage().delete_by_web_path(web_path)


async def save_audio(key: str, data: bytes) -> str:
    """TTS 音频:落地 TOS,返回公网 URL(供 ATA 拉取 + 前端播放)。"""
    return await get_audio_storage().save(key, data)


async def delete_audio_by_web_path(web_path: str) -> None:
    await get_audio_storage().delete_by_web_path(web_path)


async def save_audio_local(key: str, data: bytes) -> str:
    """TTS 音频本地持久化(播放 + 后续合成用)。返回 /api/audio/{key}。

    与 save_audio(TOS)分离:TOS 仅作 ATA 打轴的临时公网中转,打轴完成后即删;
    音频持久副本存本地盘,经 /api/audio 静态服务。
    """
    path = settings.audio_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"/api/audio/{key}"


async def delete_audio_local(web_path: str) -> None:
    prefix = "/api/audio/"
    if not web_path or not web_path.startswith(prefix):
        return
    key = web_path[len(prefix):]
    try:
        (settings.audio_dir / key).unlink(missing_ok=True)
    except Exception:
        pass
