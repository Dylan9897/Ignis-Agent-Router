# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 13:53
from typing import Optional


class OperatorError(Exception):
    """算子执行过程中发生的内部错误（非用户输入错误）"""
    def __init__(
            self,
            message: str,
            operator_name: str = "",
            original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.operator_name = operator_name
        self.original_error = original_error