"""
交易执行器 - Trader实现
"""
from typing import Dict, Any, Optional
from datetime import datetime


class Trader:
    """交易执行器
    
    负责根据交易信号执行买卖操作。
    注意：此类是独立的不继承BaseAgent。
    """
    
    def __init__(self, broker_adapter=None):
        """初始化交易执行器
        
        Args:
            broker_adapter: 券商适配器
        """
        self.broker_adapter = broker_adapter
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
    
    def generate_trading_signal(
        self,
        investment_decision: str,
        risk_assessment: Dict[str, Any] = None,
        current_price: float = 0.0,
        stock_code: str = ''
    ) -> Dict[str, Any]:
        """生成交易信号
        
        根据投资决策和风险评估生成完整的交易信号。
        
        Args:
            investment_decision: 投资决策 (强烈买入/买入/观望/卖出/强烈卖出)
            risk_assessment: 风险评估结果 {
                'risk_level': str,  # LOW/MEDIUM/HIGH
                'risk_score': float,
                'stop_loss': float,
                'position_size': float
            }
            current_price: 当前价格
            stock_code: 股票代码
            
        Returns:
            交易信号 {
                'action': str,  # BUY/SELL/HOLD
                'entry_price': float,
                'stop_loss': float,
                'take_profit': float,
                'position_size': float,
                'quantity': int,
                'reasoning': str
            }
        """
        risk_level = 'MEDIUM'
        position_size = 0.15
        stop_loss = 0.0
        
        if risk_assessment:
            risk_level = risk_assessment.get('risk_level', 'MEDIUM')
            position_size = risk_assessment.get('position_size', 0.15)
            stop_loss = risk_assessment.get('stop_loss', 0.0)
        
        if '买入' in investment_decision:
            action = 'BUY'
        elif '卖出' in investment_decision:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        entry_price = current_price
        
        if stop_loss == 0.0 and current_price > 0:
            if risk_level == 'LOW':
                stop_loss = current_price * 0.95
            elif risk_level == 'MEDIUM':
                stop_loss = current_price * 0.92
            else:
                stop_loss = current_price * 0.90
        
        take_profit = current_price * 1.15 if current_price > 0 else 0.0
        
        quantity = 0
        if action == 'BUY' and position_size > 0 and current_price > 0:
            quantity = int(position_size * 100000 / current_price / 100) * 100
        
        reasoning = f"基于{investment_decision}决策，风险等级{risk_level}，建议仓位{position_size*100:.0f}%"
        
        return {
            'action': action,
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'position_size': position_size,
            'quantity': quantity,
            'reasoning': reasoning,
            'timestamp': datetime.now().isoformat()
        }
    
    def execute_buy(self, stock_code: str, quantity: int, price: float) -> Dict[str, Any]:
        """执行买入
        
        Args:
            stock_code: 股票代码
            quantity: 数量
            price: 价格
            
        Returns:
            交易结果 {
                'success': bool,
                'order_id': str,
                'filled_price': float,
                'filled_quantity': int,
                'error': str
            }
        """
        if self.broker_adapter is None:
            return {
                'success': True,
                'order_id': f'ORD_BUY_{stock_code}_{datetime.now().strftime("%Y%m%d%H%M%S")}',
                'filled_price': price,
                'filled_quantity': quantity,
                'message': f'模拟买入: {stock_code} x {quantity} @ {price}'
            }
        
        try:
            order_result = self.broker_adapter.buy(stock_code, quantity, price)
            order_id = order_result.get('order_id', '')
            
            if order_result.get('status') == 'filled':
                self._update_position(stock_code, quantity, price)
            
            return {
                'success': True,
                'order_id': order_id,
                'filled_price': order_result.get('filled_price', price),
                'filled_quantity': order_result.get('filled_quantity', quantity),
                'error': ''
            }
        except Exception as e:
            return {
                'success': False,
                'order_id': '',
                'filled_price': 0.0,
                'filled_quantity': 0,
                'error': str(e)
            }
    
    def execute_sell(self, stock_code: str, quantity: int, price: float) -> Dict[str, Any]:
        """执行卖出
        
        Args:
            stock_code: 股票代码
            quantity: 数量
            price: 价格
            
        Returns:
            交易结果 {
                'success': bool,
                'order_id': str,
                'filled_price': float,
                'filled_quantity': int,
                'error': str
            }
        """
        if self.broker_adapter is None:
            return {
                'success': True,
                'order_id': f'ORD_SELL_{stock_code}_{datetime.now().strftime("%Y%m%d%H%M%S")}',
                'filled_price': price,
                'filled_quantity': quantity,
                'message': f'模拟卖出: {stock_code} x {quantity} @ {price}'
            }
        
        try:
            order_result = self.broker_adapter.sell(stock_code, quantity, price)
            order_id = order_result.get('order_id', '')
            
            if order_result.get('status') == 'filled':
                self._update_position(stock_code, -quantity, price)
            
            return {
                'success': True,
                'order_id': order_id,
                'filled_price': order_result.get('filled_price', price),
                'filled_quantity': order_result.get('filled_quantity', quantity),
                'error': ''
            }
        except Exception as e:
            return {
                'success': False,
                'order_id': '',
                'filled_price': 0.0,
                'filled_quantity': 0,
                'error': str(e)
            }
    
    def get_position(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取持仓
        
        Args:
            stock_code: 股票代码
            
        Returns:
            持仓信息 {
                'stock_code': str,
                'quantity': int,
                'avg_price': float,
                'current_value': float,
                'unrealized_pnl': float
            }
        """
        if stock_code in self.positions:
            return self.positions[stock_code]
        
        return {
            'stock_code': stock_code,
            'quantity': 0,
            'avg_price': 0.0,
            'current_value': 0.0,
            'unrealized_pnl': 0.0
        }
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否成功
        """
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
            return True
        return False
    
    def _update_position(self, stock_code: str, quantity_change: int, price: float):
        """更新持仓
        
        Args:
            stock_code: 股票代码
            quantity_change: 数量变化
            price: 成交价格
        """
        if stock_code not in self.positions:
            self.positions[stock_code] = {
                'stock_code': stock_code,
                'quantity': 0,
                'avg_price': 0.0,
                'total_cost': 0.0
            }
        
        pos = self.positions[stock_code]
        
        if quantity_change > 0:
            new_total_cost = pos['total_cost'] + quantity_change * price
            new_quantity = pos['quantity'] + quantity_change
            pos['avg_price'] = new_total_cost / new_quantity if new_quantity > 0 else 0.0
            pos['quantity'] = new_quantity
            pos['total_cost'] = new_total_cost
        else:
            sell_qty = min(abs(quantity_change), pos['quantity'])
            pos['quantity'] -= sell_qty
            pos['total_cost'] = pos['avg_price'] * pos['quantity']
        
        if pos['quantity'] == 0:
            del self.positions[stock_code]