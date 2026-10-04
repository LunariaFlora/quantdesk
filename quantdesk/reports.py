"""Validate imported research reports before they can enter the experiment library."""
import json
import math
import re
from datetime import date
from pathlib import Path
from .strategies import validate
from .backtest import config


def read_report(path):
    path=Path(path)
    if path.stat().st_size>100_000_000:
        raise ValueError('单份报告不能超过 100 MB')
    def invalid(value):raise ValueError('报告含非有限数值：'+value)
    body=json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=invalid)
    required={'strategy','config','dataset','summary','curve','orders','trades','round_trips','engine_version','assumptions'}
    if not isinstance(body,dict) or not required.issubset(body):raise ValueError('不是完整的桌面版报告')
    body['strategy']=validate(body['strategy'])
    settings=config(body['config'])
    body['config']=settings
    def finite(obj):
        if isinstance(obj,float) and not math.isfinite(obj):raise ValueError('报告含非有限数值')
        if isinstance(obj,dict):
            for value in obj.values():finite(value)
        elif isinstance(obj,list):
            for value in obj:finite(value)
    finite(body)
    dataset=body['dataset']
    if not isinstance(dataset,dict) or not isinstance(dataset.get('symbol'),str) or not re.fullmatch('[0-9a-f]{64}',dataset.get('metadata',{}).get('sha256','')):
        raise ValueError('报告缺少数据代码或有效哈希')
    for key in ('curve','orders','trades','round_trips'):
        if not isinstance(body[key],list) or len(body[key])>500000:raise ValueError('报告记录列表无效')
    if not body['curve']:raise ValueError('报告缺少资产曲线')
    fields={'date','open','high','low','close','volume','equity','benchmark','cash','shares','market_value','realized_pnl','unrealized_pnl','pnl','drawdown','return_pct',
            'sma_fast','sma_slow','ema_fast','ema_slow','bb_upper','bb_lower','rsi','macd','macd_signal','atr'}
    previous=''
    for row in body['curve']:
        if not isinstance(row,dict) or not fields.issubset(row):raise ValueError('报告日线或指标字段不完整')
        current=date.fromisoformat(row['date']).isoformat()
        if current<=previous:raise ValueError('报告日期乱序或重复')
        previous=current
        numeric=fields-{'date'}
        if any(row[k] is not None and (isinstance(row[k],bool) or not isinstance(row[k],(int,float))) for k in numeric):raise ValueError('报告数值字段类型无效')
        try:
            if abs(row['cash']+row['market_value']-row['equity'])>max(1e-6,abs(row['equity'])*1e-10):raise ValueError('报告现金与资产账本不一致')
            if abs(row['realized_pnl']+row['unrealized_pnl']-row['pnl'])>max(1e-6,settings['capital']*1e-10):raise ValueError('报告盈亏账本不一致')
        except TypeError:raise ValueError('报告账本含空值') from None
    summary=body['summary']
    required_summary={'return_pct','annualized_return_pct','max_drawdown_pct','sharpe','win_rate_pct','profit_loss_ratio','equity','pnl','trades','start','end'}
    if not isinstance(summary,dict) or not required_summary.issubset(summary):raise ValueError('报告绩效字段不完整')
    for key in required_summary-{'start','end'}:
        if summary[key] is not None and (isinstance(summary[key],bool) or not isinstance(summary[key],(int,float))):raise ValueError('报告绩效类型无效')
    if any(summary[k] is None for k in ('return_pct','equity','pnl','trades')):raise ValueError('报告核心绩效不能为空')
    if summary['start']!=body['curve'][0]['date'] or summary['end']!=body['curve'][-1]['date'] or summary['equity']!=body['curve'][-1]['equity']:
        raise ValueError('报告摘要与曲线不一致')
    schemas={'trades':{'date','side','price','quantity','fee','cash','reason','signal_date'},
             'orders':{'id','signal_date','date','side','status','quantity','price','reason'},
             'round_trips':{'entry_date','exit_date','quantity','entry_price','exit_price','pnl','return_pct','holding_days'}}
    for section,keys in schemas.items():
        for row in body[section]:
            if not isinstance(row,dict) or not keys.issubset(row):raise ValueError('报告成交或订单字段不完整')
            if section in ('trades','orders') and row['side'] not in ('买入','卖出'):raise ValueError('报告交易方向无效')
            for key in keys & {'price','quantity','fee','cash','entry_price','exit_price','pnl','return_pct','holding_days'}:
                if row[key] is not None and (isinstance(row[key],bool) or not isinstance(row[key],(int,float))):raise ValueError('报告成交数值类型无效')
            if section=='trades':date.fromisoformat(row['date'])
    if not isinstance(body['assumptions'],dict):raise ValueError('报告缺少计算口径')
    body.pop('id',None)
    body['assumptions']['imported_report']='已检查格式与账户恒等式；未重新下载原始数据或认证外部报告来源'
    return body
