# Build data/metro.json: Nanjing metro station->line table (curated reference)
# plus per-day-type operating-hour envelope used by the realistic-mode metro feeder model.
# -*- coding: utf-8 -*-
import json, os
ROOT=os.path.dirname(os.path.abspath(__file__))+'/..'
LINES={
'1':'八卦洲大桥南 笆斗山 燕子矶 吉祥庵 晓庄 迈皋桥 红山动物园 南京站 新模范马路 玄武门 鼓楼 珠江路 新街口 张府园 三山街 中华门 安德门 天隆寺 软件大道 花神庙 南京南站 双龙大道 河定桥 胜太路 百家湖 小龙湾 竹山路 天印大道 龙眠大道 南医大江苏经贸学院 南京交院 中国药科大学',
'2':'鱼嘴 天保街 青莲街 螺塘路 油坊桥 雨润大街 元通 奥体东 兴隆大街 集庆门大街 云锦路 莫愁湖 汉中门 上海路 新街口 大行宫 西安门 明故宫 苜蓿园 下马坊 孝陵卫 钟灵街 马群 金马路 仙鹤门 学则路 仙林中心 羊山公园 南大仙林校区 经天路',
'3':'林场 星火路 东大成贤学院 泰冯路 天润城 柳洲东路 上元门 五塘广场 小市 南京站 新庄 鸡鸣寺 浮桥 大行宫 常府街 夫子庙 武定门 雨花门 卡子门 大明路 明发广场 南京南站 宏运大道 胜太西路 天元西路 九龙湖 诚信大道 东大九龙湖校区 秣周东路 上秦淮西 秣陵',
'4':'龙江 草场门 云南路 鼓楼 鸡鸣寺 九华山 岗子村 蒋王庙 王家湾 聚宝山 徐庄苏宁总部 金马路 汇通路 灵山 东流 孟北 西岗桦墅 仙林湖',
'5':'方家营 南京西站 静海寺 下关 盐仓桥 福建路 虹桥 青春广场 云南路 五台山 上海路 朝天宫 三山街 夫子庙 通济门 光华门 石门坎 七桥瓮 大校场 神机营 东山香樟园 文靖路 东山 新亭路 竹山路 科宁路 前庄 诚信大道 九龙湖南 吉印大道',
'6':'南京南站 夹岗 机场跑道旧址 市中医院 应天东街 中和桥 光华门 明故宫 富贵山 岗子村 花园路 红山新城 营苑南路 万寿 燕江新城 兴学路 兴智街 十月广场 金陵石化 栖霞山',
'7':'仙新路 尧化门 尧化新村 丁家庄南 丁家庄 万寿 晓庄 幕府山 五塘广场 幕府西路 钟阜路 福建路 古平岗 草场门 清凉山 莫愁湖 大士茶亭 南湖 应天大街 梦都大街东 新城科技园 中胜 嘉陵江东街 永初路 太清路 螺塘路 西善桥',
'10':'雨山路 文德路 龙华路 南京工业大学 浦口万汇城 临江青奥体育公园 江心洲 绿博园 梦都大街 奥体中心 元通 中胜 小行 安德门 共青团路 雨花台 卡子门 机场跑道旧址 大校场 承天大道 高桥门 杨庄 石杨路 东麒路',
'S1':'南京南站 翠屏山 河海大学佛城西路 吉印大道 正方中路 翔宇路北 翔宇路南 禄口机场 空港新城江宁',
'S3':'南京南站 景明佳园 铁心桥 春江路 贾西 油坊桥 永初路 平良大街 吴侯街 高庙路 天保 刘村 马骡圩 兰花塘 双垅 石碛河 桥林新城 林山 高家冲',
'S6':'马群 百水桥 麒麟门 东郊小镇 古泉 南京猿人洞 汤山 泉都大街 黄梅 童世界 华阳 崇明 句容',
'S7':'空港新城江宁 柘塘 空港新城溧水 群力 卧龙湖 溧水 中山湖 幸庄 无想山',
'S8':'长江大桥北 毛纺厂路 泰山新村 泰冯路 高新开发区 信息工程大学 卸甲甸 大厂 葛塘 长芦 化工园 六合开发区 龙池 雄州 凤凰山公园 方州广场 沈桥 八百桥 金牛湖',
'S9':'翔宇路南 铜山 石湫 明觉 团结圩 高淳',
'S2':'西善桥 雨花经济开发区 板桥 板桥南 江宁镇 江宁滨江开发区 牧龙 铜井 慈湖高新区 湖北路二中 湖南路安工大 雨山东路 阳湖 马鞍山经开区 姑孰 太白',
}
st={}
for ln,names in LINES.items():
    for n in names.split():
        st.setdefault(n,[])
        if ln not in st[n]: st[n].append(ln)
# order lines: urban numeric first then S
def keyf(l): return (1 if l.startswith('S') else 0, int(l[1:]) if l.startswith('S') else int(l))
stations={n:','.join(sorted(ls,key=keyf)) for n,ls in st.items()}
hours={
 'weekday':{'first':1785,'close':1410,'feeder':90,'sOffset':-55},
 'weekend':{'first':1785,'close':1455,'feeder':90,'sOffset':-40},
 'holiday':{'first':1785,'close':1485,'feeder':100,'sOffset':-30},
}
metro={'stations':stations,'hours':hours,'note':'envelope: central last-train pass; S-lines close earlier (sOffset). first=morning resumption 05:45+1d.'}
json.dump(metro,open(ROOT+'/data/metro.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
print("metro.json written:", len(stations), "stations")
