"""
智能体基类 - AgentConfig, BaseAgent
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


@dataclass
class AgentConfig:
    """智能体配置类
    
    Attributes:
        name: 智能体名称
        role: 角色描述
        llm_adapter: LLM适配器
        system_prompt: 系统提示词
        temperature: 生成温度
        max_tokens: 最大token数
    """
    name: str
    role: str
    llm_adapter: Any = None
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048


class BaseAgent(ABC):
    """智能体基类
    
    所有智能体需继承此类。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化智能体
        
        Args:
            config: 智能体配置
        """
        self.config = config
        self.name = config.name
        self.role = config.role
        self._llm = config.llm_adapter
    
    @abstractmethod
    def _create_system_prompt(self) -> str:
        """创建系统提示词
        
        Returns:
            系统提示词字符串
        """
        pass
    
    @abstractmethod
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据
        
        Args:
            inputs: 输入字典
            
        Returns:
            格式化后的用户消息字符串
        """
        pass
    
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """调用LLM获取响应
        
        Args:
            messages: 消息列表 [{'role': 'user'/'assistant'/'system', 'content': '...'}]
            
        Returns:
            LLM响应文本
        """
        if self._llm is None:
            return "错误: 未配置LLM适配器"
        
        try:
            # 调用LLM的chat方法
            response = self._llm.chat(messages)
            return response
        except Exception as e:
            return f"错误: LLM调用失败 - {str(e)}"
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """主执行方法
        
        Args:
            inputs: 输入数据字典
            
        Returns:
            {'success': bool, 'output': str, 'error': str}
        """
        try:
            # 创建系统提示词
            system_prompt = self._create_system_prompt()
            
            # 处理输入
            user_message = self._process_input(inputs)
            
            # 构建消息列表
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message},
            ]
            
            # 调用LLM
            output = self._call_llm(messages)
            
            return {
                'success': True,
                'output': output,
                'error': ''
            }
            
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }
    
    def chat(self, message: str, **kwargs) -> str:
        """发送消息并获取回复
        
        Args:
            message: 用户消息
            **kwargs: 其他参数
            
        Returns:
            智能体回复
        """
        messages = [
            {'role': 'system', 'content': self._create_system_prompt()},
            {'role': 'user', 'content': message},
        ]
        return self._call_llm(messages)
    
    def think(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """思考并处理上下文
        
        Args:
            context: 上下文字典
            
        Returns:
            处理结果
        """
        result = self.run(context)
        return result
    
    def get_system_prompt(self) -> str:
        """获取系统提示词
        
        Returns:
            系统提示词
        """
        return self._create_system_prompt()