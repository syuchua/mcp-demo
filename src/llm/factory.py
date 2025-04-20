# src/llm/factory.py
from typing import Dict, Optional, Type
from .base import LLMProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .google import GoogleProvider
from ..log import logger

class LLMFactory:
    """LLM 提供者工厂"""
    
    _registry: Dict[str, Type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider
    }
    
    # 官方 API 端点
    _official_endpoints = {
        "openai": ["api.openai.com"],
        "anthropic": ["api.anthropic.com", "claude.ai"],
        "google": ["generativelanguage.googleapis.com", "ai.googleapis.com"]
    }
    
    @classmethod
    def register(cls, name: str, provider_class: Type[LLMProvider]) -> None:
        """注册新的 LLM 提供者"""
        cls._registry[name] = provider_class
    
    @classmethod
    def create(cls, provider_name: str, api_key: str, base_url: Optional[str] = None) -> LLMProvider:
        """创建 LLM 提供者实例"""
        if provider_name not in cls._registry:
            raise ValueError(f"未知的 LLM 提供者: {provider_name}")
        
        provider_class = cls._registry[provider_name]
        return provider_class(api_key, base_url)
    
    @classmethod
    def get_provider_for_model(cls, model_name: str, api_key: str, base_url: Optional[str] = None) -> LLMProvider:
        """根据模型名称和基础 URL 选择合适的提供者"""
        import urllib.parse
        
        # 基于模型名称的初步映射
        model_prefix_map = {
            "gpt": "openai",
            "claude": "anthropic",
            "gemini": "google",
            "text-bison": "google",
            "palm": "google"
        }
        
        # 1. 确定初始提供者候选(基于模型名)
        provider_candidate = None
        for prefix, provider in model_prefix_map.items():
            if model_name.lower().startswith(prefix):
                provider_candidate = provider
                break
        
        # 2. 如果有 base_url，检查是否是官方端点
        if base_url:
            try:
                # 解析 base_url 获取 hostname
                parsed_url = urllib.parse.urlparse(base_url)
                hostname = parsed_url.netloc.lower()
                
                # 检查是否匹配任何官方端点
                is_official_endpoint = False
                matched_provider = None
                
                for provider, domains in cls._official_endpoints.items():
                    if any(domain in hostname for domain in domains):
                        is_official_endpoint = True
                        matched_provider = provider
                        break
                
                if is_official_endpoint:
                    # 如果是官方端点，使用对应的提供者
                    logger.info(f"使用官方端点 {hostname} 对应的 {matched_provider} 提供者")
                    return cls.create(matched_provider, api_key, base_url)
                else:
                    # 如果不是官方端点，默认使用 OpenAI 提供者
                    # 这是因为大多数代理服务都使用 OpenAI 兼容的 API 格式
                    logger.info(f"使用非官方端点 {hostname}，默认以 OpenAI 兼容接口处理")
                    return cls.create("openai", api_key, base_url)
            except Exception as e:
                logger.warning(f"解析 base_url 时出错: {e}，回退到基于模型名称的选择")
        
        # 3. 如果没有 base_url 或解析失败，使用基于模型名称的选择
        if provider_candidate:
            logger.info(f"根据模型名 {model_name} 选择 {provider_candidate} 提供者")
            return cls.create(provider_candidate, api_key, base_url)
        
        # 4. 默认使用 OpenAI 提供者
        logger.info(f"无法确定提供者，默认使用 OpenAI 提供者处理模型 {model_name}")
        return cls.create("openai", api_key, base_url)