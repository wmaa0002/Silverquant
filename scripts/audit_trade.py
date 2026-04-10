#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易审计脚本 - audit_trade.py

用法：
    python scripts/audit_trade.py                    # 审计今日（仅报告）
    python scripts/audit_trade.py --fix              # 执行修复
    python scripts/audit_trade.py --date 20260327     # 审计指定日期
    python scripts/audit_trade.py --feishu            # 发送飞书报告
"""

import os, sys, re, json, argparse
from datetime import datetime, date
from typing import Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import duckdb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'Astock3.duckdb')
SIGNALS_FILE = os.path.join(PROJECT_ROOT, 'signals', 'scan_signals_v2.py')
INIT_CASH = 500000.0
TOLERANCE = 1.0

class AuditResult:
    def __init__(self, check_item, check_type, severity, status,
                 detail="", fix_action="", before_val="", after_val=""):
        self.check_item = check_item
        self.check_type = check_type
        self.severity = severity
        self.status = status
        self.detail = detail
        self.fix_action = fix_action
        self.before_val = before_val
        self.after_val = after_val
    def to_dict(self):
        return {k: getattr(self, k) for k in 
                ['check_item','check_type','severity','status','detail','fix_action','before_val','after_val']}

class TradeAuditor:
    def __init__(self, db_path, audit_date=None, dry_run=True):
        self.conn = duckdb.connect(db_path, read_only=False)
        self.audit_date = audit_date or date.today().strftime('%Y-%m-%d')
        self.dry_run = dry_run
        self.results: List[AuditResult] = []
        self.fixed_count = self.manual_count = self.ok_count = 0

    def _ok(self, item, detail):
        self.results.append(AuditResult(item,'COMPLETENESS','INFO','OK',detail))
        self.ok_count += 1

    def _fix(self, item, detail, action, before, after):
        self.results.append(AuditResult(item,'COMPLETENESS','ERROR','AUTO_FIXED',detail,action,before,after))
        self.fixed_count += 1

    def _warn(self, item, detail, action="", before="", after=""):
        self.results.append(AuditResult(item,'LOGIC','WARNING','MANUAL_FIX',detail,action,before,after))
        self.manual_count += 1

    def _manual(self, item, detail, action="", before="", after=""):
        self.results.append(AuditResult(item,'COMPLETENESS','ERROR','MANUAL_FIX',detail,action,before,after))
        self.manual_count += 1

    # ---- A1: portfolio_daily 今日记录 ----
    def check_a1(self):
        r = self.conn.execute(
            "SELECT COUNT(*) FROM portfolio_daily WHERE date = ?",[self.audit_date]).fetchone()
        if r[0] == 0:
            self._fix_a1_insert()
        elif r[0] > 1:
            self._manual('A1','portfolio_daily 今日有%d条（应1条）'%r[0],'需人工去重')
        else:
            self._ok('A1','有1条记录')

    def _fix_a1_insert(self):
        nid = self.conn.execute('SELECT COALESCE(MAX(id),0) FROM portfolio_daily').fetchone()[0]+1
        hold = self.conn.execute("SELECT code,name,shares,buy_price FROM positions WHERE status='holding'").fetchall()
        sold = self.conn.execute("SELECT code,name,profit_loss FROM positions WHERE status='sold'").fetchall()
        cost = sum(h[2]*h[3]*1.0005 for h in hold)
        val = 0.0
        for h in hold:
            cp = self.conn.execute(f"SELECT close FROM dwd_daily_price WHERE ts_code='{h[0]}' AND trade_date='{self.audit_date}'").fetchone()
            if cp: val += h[2]*float(cp[0])
        closed = sum(float(s[2]) for s in sold if s[2] is not None) or 0.0
        pnl = val-cost; tpnl = pnl+closed; avail = INIT_CASH-cost+closed
        ratio = val/INIT_CASH*100 if INIT_CASH else 0
        tv = val+avail
        notes = "持仓%d只: %s"%(len(hold),','.join(h[1] for h in hold)) if hold else "空仓"
        if sold: notes += " | 已卖%d只: %s"%(len(sold),','.join(s[1] for s in sold))
        if not self.dry_run:
            self.conn.execute(f"""INSERT INTO portfolio_daily (id,date,init_cash,position_cost,position_value,position_pnl,closed_pnl,total_pnl,available_cash,position_ratio,total_value,notes) VALUES ({nid},'{self.audit_date}',{INIT_CASH},{cost},{val},{pnl},{closed},{tpnl},{avail},{ratio},{tv},'{notes}')""")
        self._fix('A1','补插portfolio_daily','INSERT','无记录','市值=%.0f 仓位=%.1f%%'%(val,ratio))

    # ---- A2: total_value 有值 ----
    def check_a2(self):
        r = self.conn.execute("SELECT total_value FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
        if not r or r[0] is None:
            pv = self.conn.execute("SELECT position_value FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
            ac = self.conn.execute("SELECT available_cash FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
            if pv and ac:
                tv = float(pv[0])+float(ac[0])
                if not self.dry_run:
                    self.conn.execute("UPDATE portfolio_daily SET total_value=? WHERE date=?",[tv,self.audit_date])
                self._fix('A2','total_value为空','UPDATE total_value','','%.2f'%tv)
            return
        self._ok('A2','total_value=%.2f'%float(r[0]))

    # ---- A3: total_value = pos + avail ----
    def check_a3(self):
        r = self.conn.execute("SELECT total_value,position_value,available_cash FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
        if not r: return
        tv, pv, ac = float(r[0] or 0), float(r[1] or 0), float(r[2] or 0)
        diff = abs(tv-(pv+ac))
        if diff >= TOLERANCE:
            exp = pv+ac
            if not self.dry_run: self.conn.execute("UPDATE portfolio_daily SET total_value=? WHERE date=?",[exp,self.audit_date])
            self._fix('A3','total_value不平衡 误差%.2f'%diff,'UPDATE total_value','%.2f'%tv,'%.2f'%exp)
        else:
            self._ok('A3','平衡（误差%.4f）'%diff)

    # ---- A4: total_pnl = pos_pnl + closed_pnl ----
    def check_a4(self):
        r = self.conn.execute("SELECT total_pnl,position_pnl,closed_pnl FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
        if not r: return
        tp,pp,cp = float(r[0] or 0), float(r[1] or 0), float(r[2] or 0)
        diff = abs(tp-(pp+cp))
        if diff >= TOLERANCE:
            exp = pp+cp
            if not self.dry_run: self.conn.execute("UPDATE portfolio_daily SET total_pnl=? WHERE date=?",[exp,self.audit_date])
            self._fix('A4','total_pnl不平衡 误差%.2f'%diff,'UPDATE total_pnl','%.2f'%tp,'%.2f'%exp)
        else:
            self._ok('A4','pnl平衡（误差%.4f）'%diff)

    # ---- A5: portfolio_daily_strategy 记录 ----
    def check_a5(self):
        strats = [s[0] for s in self.conn.execute("SELECT DISTINCT strategy FROM positions WHERE status='holding'").fetchall()]
        for s in strats:
            cnt = self.conn.execute("SELECT COUNT(*) FROM portfolio_daily_strategy WHERE date=? AND strategy=?",[self.audit_date,s]).fetchone()[0]
            if cnt == 0:
                self._fix_a5_insert(s)
            elif cnt > 1:
                self._manual('A5','策略"%s"有%d条记录'%(s[:6],cnt),'需人工去重')
            else:
                self._ok('A5-'+s[:6],'%s有1条'%s)

    def _fix_a5_insert(self, strat):
        nid = self.conn.execute('SELECT COALESCE(MAX(id),0) FROM portfolio_daily_strategy').fetchone()[0]+1
        row = self.conn.execute(f"""SELECT SUM(p.shares*p.buy_price*1.0005),SUM(p.shares*dp.close) FROM positions p JOIN dwd_daily_price dp ON p.code=dp.ts_code AND dp.trade_date='{self.audit_date}' WHERE p.status='holding' AND p.strategy=?""",[strat]).fetchone()
        cost,val = float(row[0] or 0), float(row[1] or 0)
        pnl = val-cost
        closed = self.conn.execute("SELECT SUM(profit_loss) FROM positions WHERE status='sold' AND strategy=?",[strat]).fetchone()[0] or 0.0
        tpnl = pnl+closed
        cnt = self.conn.execute("SELECT COUNT(*) FROM positions WHERE strategy=?",[strat]).fetchone()[0]
        if not self.dry_run:
            self.conn.execute(f"""INSERT INTO portfolio_daily_strategy (id,date,strategy,position_cost,position_value,position_pnl,closed_pnl,total_pnl,trade_count,notes) VALUES ({nid},'{self.audit_date}','{strat}',{cost},{val},{pnl},{closed},{tpnl},{cnt},'持仓市值={val:.0f}，成本={cost:.0f}')""")
        self._fix('A5','策略"%s"补录'%strat,'INSERT strategy record','无记录','市值=%.0f'%val)

    # ---- A6: strategy pnl balance ----
    def check_a6(self):
        for strat,tp,pp,cp in self.conn.execute("SELECT strategy,total_pnl,position_pnl,closed_pnl FROM portfolio_daily_strategy WHERE date=?",[self.audit_date]).fetchall():
            exp = float(pp or 0)+float(cp or 0)
            diff = abs(float(tp or 0)-exp)
            if diff >= TOLERANCE:
                if not self.dry_run: self.conn.execute("UPDATE portfolio_daily_strategy SET total_pnl=? WHERE date=? AND strategy=?",[exp,self.audit_date,strat])
                self._fix('A6',strat[:6]+' pnl不平衡','UPDATE total_pnl','%.2f'%float(tp or 0),'%.2f'%exp)
            else:
                self._ok('A6-'+strat[:6],'pnl平衡')

    # ---- A7: no duplicate holding ----
    def check_a7(self):
        dupes = self.conn.execute("SELECT code,COUNT(*) FROM positions WHERE status='holding' GROUP BY code HAVING COUNT(*)>1").fetchall()
        if dupes:
            for d in dupes: self._manual('A7','%s有%d条holding记录'%(d[0],d[1]),'需人工合并')
        else:
            self._ok('A7','无重复holding')

    # ---- A8: all holdings have today's price ----
    def check_a8(self):
        miss = [(r[0],r[1]) for r in self.conn.execute(
            "SELECT p.code,p.name FROM positions p LEFT JOIN dwd_daily_price dp ON p.code=dp.ts_code AND dp.trade_date=? WHERE p.status='holding' AND dp.close IS NULL",[self.audit_date]).fetchall()]
        if miss:
            # 如果是今天且无数据，说明流水线未更新，忽略
            is_today = self.audit_date == date.today().strftime('%Y-%m-%d')
            if is_today:
                self._ok('A8','今日(%s)无交易数据，流水线尚未更新'%self.audit_date)
            else:
                for c,n in miss: self._manual('A8','%s(%s)无%s收盘价'%(n,c,self.audit_date),'补充价格数据')
        else:
            self._ok('A8','所有持仓股票价格完整')

    # ---- A9: sold records have profit_loss ----
    def check_a9(self):
        miss = [(r[0],r[1]) for r in self.conn.execute("SELECT code,name FROM positions WHERE status='sold' AND profit_loss IS NULL").fetchall()]
        if miss:
            for c,n in miss: self._manual('A9','%s(%s) profit_loss为空'%(n,c),'需人工计算')
        else:
            self._ok('A9','所有sold记录profit_loss完整')

    # ---- B1: position_ratio range ----
    def check_b1(self):
        r = self.conn.execute("SELECT position_ratio FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
        if not r or r[0] is None: return
        ratio = float(r[0])
        if ratio < 0 or ratio > 100:
            self._manual('B1','position_ratio=%.1f%%（应0-100%%）'%ratio,'检查持仓市值计算')
        else:
            self._ok('B1','仓位正常 (%.1f%%)'%ratio)

    # ---- B2: stop loss warning ----
    def check_b2(self):
        warns = []
        for code,name,shares,buy_price,strat,cur in self.conn.execute(
            "SELECT p.code,p.name,p.shares,p.buy_price,p.strategy,dp.close FROM positions p JOIN dwd_daily_price dp ON p.code=dp.ts_code AND dp.trade_date=? WHERE p.status='holding'",[self.audit_date]).fetchall():
            c = shares*float(buy_price)*1.0005; v = shares*float(cur); pct = (v-c)/c*100 if c else 0
            if pct < -5.0: warns.append('%s %.1f%%'%(name,pct))
        if warns:
            self._warn('B2','以下持仓亏损>5%%但未止损: %s'%(', '.join(warns)),'需人工确认')
        else:
            self._ok('B2','无异常止损警告')

    # ---- B3: available_cash not negative ----
    def check_b3(self):
        r = self.conn.execute("SELECT available_cash FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
        if r and r[0] is not None and float(r[0]) < 0:
            self._manual('B3','available_cash=%.2f'%float(r[0]),'检查资金计算')
        elif r:
            self._ok('B3','可用资金正常 (%.0f)'%float(r[0]))

    # ---- B4: total_value > 0 ----
    def check_b4(self):
        r = self.conn.execute("SELECT total_value FROM portfolio_daily WHERE date=?",[self.audit_date]).fetchone()
        if r and r[0] is not None and float(r[0]) <= 0:
            self._manual('B4','total_value=%.2f'%float(r[0]),'检查持仓和资金')
        elif r:
            self._ok('B4','账户总值正常 (%.0f)'%float(r[0]))

    # ---- C1: signal field consistency ----
    def check_c1(self):
        if not os.path.exists(SIGNALS_FILE):
            self._warn('C1','信号文件不存在: '+SIGNALS_FILE,'','文件缺失','无法检查')
            return
        with open(SIGNALS_FILE) as f: src = f.read()
        issues = []
        # 查找 sell_condition 中用了 signal_buy_xxx
        for m in re.finditer(r'def (get_\w+_sell_signal|common_sell_signal)\(.*?\):(.*?)(?=\ndef |\Z)', src, re.DOTALL):
            fname, body = m.group(1), m.group(2)
            for cond in re.findall(r'sell_condition\s*=\s*([^#\n]+)', body):
                if 'signal_buy_' in cond and 'or signal_sell' not in cond:
                    issues.append('%s中sell_condition包含signal_buy' % fname)
        if issues:
            self._warn('C1','signal字段使用错误: %s'%(issues[0]),'检查源码signal_sell/buy字段')
        else:
            self._ok('C1','signal字段使用一致')

    # ---- C2: stop loss coverage ----
    def check_c2(self):
        if not os.path.exists(SIGNALS_FILE): return
        with open(SIGNALS_FILE) as f: src = f.read()
        m = re.search(r'def common_sell_signal\(.*?\):(.*?)(?=\ndef |\Z)', src, re.DOTALL)
        if not m:
            self._ok('C2','未找到止损逻辑'); return
        binds = re.findall(r"(?:trade_strategy|strategy)\s*==\s*['\"]([^'\"]+)['\"]", m.group(1))
        if binds:
            self._warn('C2','止损绑定了策略: %s'%binds,'修改scan_signals_v2.py止损逻辑')
        else:
            self._ok('C2','止损无策略绑定')

    def _ensure_table(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS trade_audit_log (
            id INTEGER PRIMARY KEY, audit_date DATE NOT NULL, check_item VARCHAR NOT NULL,
            check_type VARCHAR NOT NULL, severity VARCHAR NOT NULL, status VARCHAR NOT NULL,
            detail TEXT, fix_action TEXT, before_val TEXT, after_val TEXT,
            auditor VARCHAR DEFAULT 'audit_trade.py', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    def run_all(self):
        print("开始审计 %s，dry_run=%s" % (self.audit_date, self.dry_run))
        self._ensure_table()
        checks = [self.check_a1,self.check_a2,self.check_a3,self.check_a4,self.check_a5,
                  self.check_a6,self.check_a7,self.check_a8,self.check_a9,
                  self.check_b1,self.check_b2,self.check_b3,self.check_b4,
                  self.check_c1,self.check_c2]
        for c in checks:
            try: c()
            except Exception as e:
                print("  ! %s 执行出错: %s" % (c.__name__, e))
        for r in self.results:
            nid = self.conn.execute('SELECT COALESCE(MAX(id),0) FROM trade_audit_log').fetchone()[0]+1
            if not self.dry_run:
                self.conn.execute(f"""INSERT INTO trade_audit_log (id,audit_date,check_item,check_type,severity,status,detail,fix_action,before_val,after_val,auditor) VALUES ({nid},'{self.audit_date}','{r.check_item}','{r.check_type}','{r.severity}','{r.status}','{r.detail}','{r.fix_action}','{r.before_val}','{r.after_val}','audit_trade.py')""")
        return self.results

    def get_report(self) -> str:
        fixed = [r for r in self.results if r.status=='AUTO_FIXED']
        manual = [r for r in self.results if r.status=='MANUAL_FIX']
        ok = [r for r in self.results if r.status=='OK']
        warns = [r for r in self.results if r.severity=='WARNING']
        lines = ["📋 交易审计报告 — %s" % self.audit_date, ""]
        if fixed:
            lines.append("✅ 自动修复了 %d 项：" % len(fixed))
            for r in fixed:
                lines.append("  [%s] %s" % (r.check_item, r.detail))
                lines.append("    → %s (%s → %s)" % (r.fix_action, r.before_val, r.after_val))
            lines.append("")
        if manual:
            lines.append("⚠️ 需人工确认 %d 项：" % len(manual))
            for r in manual:
                lines.append("  [%s] %s" % (r.check_item, r.detail))
                if r.fix_action: lines.append("    → %s" % r.fix_action)
            lines.append("")
        if warns:
            lines.append("🔔 警告 %d 项：" % len(warns))
            for r in warns: lines.append("  [%s] %s" % (r.check_item, r.detail))
            lines.append("")
        lines.append("🔍 审计通过 %d 项" % len(ok))
        if self.dry_run: lines.insert(1,"⚠️ dry_run模式，仅报告不修复")
        return "\n".join(lines)

    def summary(self):
        return "审计完成: AUTO_FIX=%d, MANUAL_FIX=%d, OK=%d, 总计=%d" % (
            self.fixed_count, self.manual_count, self.ok_count, len(self.results))

    def has_issues(self) -> bool:
        return any(r.status in ('AUTO_FIXED','MANUAL_FIX') for r in self.results)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date',type=str,help='审计日期 YYYYMMDD')
    ap.add_argument('--fix',action='store_true',help='执行修复')
    ap.add_argument('--feishu',action='store_true',help='发送飞书报告')
    ap.add_argument('--report-only',action='store_true',help='仅报告')
    args = ap.parse_args()
    if args.date:
        ad = "%s-%s-%s" % (args.date[:4],args.date[4:6],args.date[6:8])
    else:
        ad = date.today().strftime('%Y-%m-%d')
    dry = not args.fix or args.report_only
    aud = TradeAuditor(DB_PATH, ad, dry_run=dry)
    aud.run_all()
    report = aud.get_report()
    print(report)
    print(aud.summary())
    # 发送飞书
    if args.feishu or (args.fix and not dry):
        try:
            from scripts.feishu_notifier import send_feishu_message
            send_feishu_message(report)
            print("✅ 飞书报告已发送")
        except Exception as e:
            print("⚠️ 飞书发送失败: %s" % e)
            print("飞书报告内容：")
            print(report)
    if not dry: print("所有修复已写入数据库")

if __name__ == '__main__':
    main()
