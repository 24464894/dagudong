"""把 raw/YYYY-MM-DD/ 的 CSV 整理成網站用的 data.json。
用法：python build_data.py raw/2026-10-30 data.json
"""
import csv, re, json, sys, collections
D=sys.argv[1]; OUT=sys.argv[2]
# 原始 CSV 會把「碁」等罕用字弄壞成 U+FFFD，依代號補回
NAME_FIX={'6776':'展碁國際','6908':'宏碁遊戲-創','6285':'啟碁','3046':'建碁','2353':'宏碁','2432':'倚天酷碁-創','8349':'恒耀','6174':'安碁','6811':'宏碁資訊','7794':'宏碁智醫','6690':'安碁資訊','8111':'立碁','8077':'洛碁'}
def rows(f): return [r for r in csv.DictReader(open(f'{D}/{f}',encoding='utf-8')) if any((v or '').strip() for v in r.values())]
def roc(s):
    s=(s or '').strip()
    if len(s)==7 and s.isdigit(): return f'{int(s[:3])+1911}-{s[3:5]}-{s[5:]}'
    return s
cos={}
def co(code,name,mkt=None):
    code=code.strip(); name=name.strip()
    c=cos.setdefault(code,{'c':code,'n':name,'m':mkt or '','p':None,'s':[]})
    if mkt and not c['m']: c['m']=mkt
    return c
# pledge
for f,m in [('43532_上市_董監質權設定.csv','上市'),('43533_上櫃_董監質權設定.csv','上櫃')]:
    for r in rows(f):
        for code,name,p in re.findall(r'(\S+)\s+(\S+)\s+([\d.]+)',r['公司名稱']):
            co(code,name,m)['p']=float(p)
pledge_date=roc(rows('43532_上市_董監質權設定.csv')[0]['出表日期'])
# control
def ctype(t):
    if '公開收購' in t: return '公開收購'
    if '私募' in t: return '私募入主'
    if '母公司' in t: return '母公司易主'
    if '轉讓' in t or '取得' in t and '股權' in t: return '股權轉讓'
    if '解任' in t: return '解任董事'
    if '辭任' in t and '改選' not in t: return '董事辭任'
    if '改派' in t or '主要股東' in t: return '法人董事易主'
    return '董事改選'
control=[]
for f,m in [('31613_上市_經營權異動.csv','上市'),('44112_上櫃_經營權異動.csv','上櫃')]:
    for r in rows(f):
        t=re.sub(r'&#8194;',' ',r['經營權異動說明']).replace('\n',' ')
        e={'c':r['公司代號'].strip(),'n':r['公司名稱'].strip(),'m':m,'d':roc(r['經營權異動日期']),'t':ctype(t),'x':t}
        control.append(e)
        co(e['c'],e['n'],m)['s'].append({'k':'control','d':e['d'],'x':f"經營權異動（{e['t']}）"})
control.sort(key=lambda e:e['d'],reverse=True)
# weekly pledge
weekly=[]
for r in rows('20610_集保_設質交付個股週統計.csv'):
    code=r['股票代號'].strip()
    if not re.fullmatch(r'\d{4}',code): continue
    try: dv=int(r['增減數額'])
    except: continue
    if dv==0: continue
    try: rate=float(r['增減比率'])
    except: rate=None
    try: iss=float(r['發行比率'])
    except: iss=None
    weekly.append({'c':code,'n':r['股票名稱'].strip(),'dv':dv,'r':rate,'i':iss})
week_date=roc(rows('20610_集保_設質交付個股週統計.csv')[0]['資料日期'])
for w in weekly:
    if w['dv']>=1_000_000:
        co(w['c'],w['n'])['s'].append({'k':'pledgeUp','d':week_date,'x':f"本週設質增加 {w['dv']//1000:,} 張（{w['r']:+.2f}%）"})
# high pledge signal
for c in cos.values():
    if c['p'] is not None and c['p']>=50:
        c['s'].append({'k':'pledgeHigh','d':pledge_date,'x':f"董監持股 {c['p']:.2f}% 已質押"})
# trading changes 11736
trade=[]
for r in rows('11736_上櫃_變更交易分盤管理停止交易.csv'):
    code=r['證券代號'].strip()
    if not code: continue
    kinds=[k for k,lab in [('變更交易','全額交割'),('分盤交易','分盤交易'),('管理股票','管理股票'),('停止交易','停止交易')] if r[k].strip()]
    labs=[{'變更交易':'全額交割','分盤交易':'分盤交易','管理股票':'管理股票','停止交易':'停止交易'}[k] for k in kinds]
    if not labs: continue
    trade.append({'c':code,'n':r['證券名稱'].strip(),'k':'、'.join(labs)})
    co(code,r['證券名稱'],'上櫃')['s'].append({'k':'trade','d':roc(r['資料日期']),'x':'交易方式變更：'+'、'.join(labs)})
# disposal
disp=[]
for r in rows('11396_上櫃_處置有價證券.csv'):
    code=r['證券代號'].strip()
    a,_,b=r['處置起訖時間'].partition('~')
    e={'c':code,'n':r['證券名稱'].strip(),'from':roc(a),'to':roc(b),'why':r['處置原因'].strip(),'d':roc(r['公布日期'])}
    disp.append(e)
    co(code,e['n'],'上櫃')['s'].append({'k':'disposal','d':e['d'],'x':f"被處置 {e['from'][5:]}～{e['to'][5:]}（{e['why']}）"})
# fines
fines=[]
for r in rows('22817_上市_證期局裁罰.csv'):
    amt=re.search(r'([\d,.]+)\s*萬元',r['裁處情形'])
    e={'c':r['股票代號'].strip(),'n':r['公司名稱'].strip(),'d':roc(r['發函日期']),'src':'金管會證期局','why':r['違規事由'].replace('\n','')[:90],'amt':float(amt.group(1).replace(',','')) if amt else None,'raw':r['裁處情形'][:60]}
    fines.append(e)
for r in rows('24280_上市_違反重訊規定.csv'):
    try: a=float(r['裁罰金額(萬)'])
    except: a=None
    fines.append({'c':r['股票代號'].strip(),'n':r['公司名稱'].strip(),'d':roc(r['發函日期']),'src':'證交所（重訊）','why':r['違規事由'].replace('\n','')[:90],'amt':a,'raw':''})
fines.sort(key=lambda e:e['d'],reverse=True)
for e in fines:
    if e['d']>='2025-10-30' and e['c']:
        amt=f"{e['amt']:g} 萬" if e['amt'] else '處分'
        co(e['c'],e['n'])['s'].append({'k':'fined','d':e['d'],'x':f"{e['src']}罰 {amt}"})
# insider
ins=[]
for f,m in [('22813_上市_內部人持股轉讓申報.csv','上市'),('22814_上櫃_內部人持股轉讓申報.csv','上櫃')]:
    for r in rows(f):
        if not r['公司代號'].strip(): continue
        hold=int(r['目前持有股數-自有持股'] or 0); sell=int((r['預定轉讓總股數-自有持股'] or '0').strip())
        e={'c':r['公司代號'].strip(),'n':r['公司名稱'].strip(),'m':m,'who':r['申請人身分'].strip(),'name':r['姓名'].strip(),'how':r['預定轉讓方式及股數-轉讓方式'].strip(),'sell':sell,'hold':hold,'period':'～'.join(roc(x) for x in r['有效轉讓期間'].split('~')),'d':roc(r['出表日期'])}
        ins.append(e)
        co(e['c'],e['n'],m)['s'].append({'k':'insider','d':e['d'],'x':f"{e['who']}{e['name']}申報轉讓 {sell//1000:,} 張"})
# announcements counts
ann={'上市':0,'上櫃':0}; clause=collections.Counter()
for f,m in [('18415_上市_每日重大訊息.csv','上市'),('18418_上櫃_每日重大訊息.csv','上櫃')]:
    for r in rows(f):
        ann[m]+=1
        k=next((v for k,v in r.items() if k and '條款' in k),'') or ''
        mm=re.search(r'第\s*(\d+)\s*款',k); clause[mm.group(1) if mm else '其他']+=1
# 產業別：從每月營收檔取
ind={}
for f in ['18420_上市_每月營收.csv','56510_上櫃_每月營收.csv']:
    try:
        for r in rows(f):
            if r['公司代號'].strip(): ind[r['公司代號'].strip()]=r['產業別'].strip()
    except FileNotFoundError: pass
for c in cos.values():
    i=ind.get(c['c'],'')
    c['i']='金融保險業' if i=='金融業' else (i or '其他')
# 修正壞字
for lst in [list(cos.values()),control,weekly,trade,disp,fines,ins]:
    for o in lst:
        if o.get('c') in NAME_FIX and '\ufffd' in o.get('n',''): o['n']=NAME_FIX[o['c']]
# dedupe signal kinds per company
for c in cos.values():
    c['k']=sorted(set(s['k'] for s in c['s']))
data={'today':'2026-10-30','pledgeDate':pledge_date,'weekDate':week_date,'cos':list(cos.values()),'control':control,'weekly':sorted(weekly,key=lambda w:-w['dv']),'trade':trade,'disp':disp,'fines':fines,'insider':ins,'ann':ann,'clause':clause.most_common(12)}
json.dump(data,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
multi=[c for c in cos.values() if len(c['k'])>=2]
multi.sort(key=lambda c:-len(c['k']))
print(len(cos),'cos; multi',len(multi))
for c in multi: print(c['c'],c['n'],c['k'])
print(ann,clause.most_common(12)); print('weekly up>=1000張',sum(1 for w in weekly if w['dv']>=1_000_000),'fines recent',sum(1 for e in fines if e['d']>='2025-10-30'))
