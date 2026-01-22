"""MinIO存储插件"""

import logging
from typing import Any, Optional
from datetime import datetime
from log_analyzer.plugins.sinks.base import AbstractSink

logger = logging.getLogger(__name__)

try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    logger.warning("MinIO库未安装，MinIOSink将不可用")


class MinIOSink(AbstractSink):
    """保存到MinIO对象存储"""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        object_prefix: str = "reports/",
        secure: bool = False,
        **kwargs
    ):
        """
        初始化MinIO存储
        
        Args:
            endpoint: MinIO端点
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket_name: 存储桶名称
            object_prefix: 对象前缀
            secure: 是否使用HTTPS
        """
        super().__init__(**kwargs)
        
        if not MINIO_AVAILABLE:
            raise ImportError("MinIO库未安装，请运行: pip install minio")
        
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.object_prefix = object_prefix.rstrip('/') + '/'
        self.secure = secure
        
        # 初始化MinIO客户端
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
    
    def save(self, data: Any, metadata: dict = None) -> Any:
        """保存到MinIO"""
        try:
            # 确保存储桶存在
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建存储桶: {self.bucket_name}")
            
            # 从metadata获取容器名称和时间戳
            container_name = 'all'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if metadata:
                container_name = metadata.get('container_name', 'all')
                timestamp = metadata.get('timestamp', timestamp)
            
            # 生成对象名称：时间_容器名.md
            object_name = f"{self.object_prefix}{timestamp}_{container_name}.md"
            
            # 上传数据
            from io import BytesIO
            data_bytes = str(data).encode('utf-8')
            data_stream = BytesIO(data_bytes)
            
            self.client.put_object(
                self.bucket_name,
                object_name,
                data_stream,
                length=len(data_bytes),
                content_type='text/markdown'
            )
            
            logger.info(f"保存到MinIO: {self.bucket_name}/{object_name}")
            return f"{self.bucket_name}/{object_name}"
            
        except S3Error as e:
            logger.error(f"MinIO操作失败: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"保存到MinIO失败: {e}", exc_info=True)
            return None
