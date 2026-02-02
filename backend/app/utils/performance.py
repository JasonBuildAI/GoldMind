"""性能监控工具 - 记录函数执行时间和错误"""
import time
import functools
from loguru import logger
from typing import Callable, Any


def log_execution_time(func: Callable) -> Callable:
    """记录函数执行时间的装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        function_name = func.__name__
        module_name = func.__module__
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 记录执行时间（超过1秒的打印警告）
            if execution_time > 1.0:
                logger.warning(
                    f"[性能警告] {module_name}.{function_name} 执行较慢: {execution_time:.2f}s"
                )
            else:
                logger.debug(
                    f"[性能] {module_name}.{function_name} 执行成功: {execution_time:.3f}s"
                )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"[性能] {module_name}.{function_name} 执行失败: {execution_time:.3f}s, "
                f"错误: {type(e).__name__}: {str(e)}"
            )
            raise
    
    return wrapper


def log_api_call(func: Callable) -> Callable:
    """记录API调用的装饰器"""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        function_name = func.__name__
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"[API] {function_name} 响应成功: {execution_time:.3f}s"
            )
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"[API] {function_name} 响应失败: {execution_time:.3f}s, 错误: {str(e)}"
            )
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        function_name = func.__name__
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"[API] {function_name} 响应成功: {execution_time:.3f}s"
            )
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"[API] {function_name} 响应失败: {execution_time:.3f}s, 错误: {str(e)}"
            )
            raise
    
    # 根据函数类型返回对应的wrapper
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# 导入asyncio用于检查协程函数
import asyncio
