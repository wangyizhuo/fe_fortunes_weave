import json, csv, re
W = {
'木製の剣':'木剑','青銅の剣':'青铜剑','鉄の剣':'铁剑','斬馬刀':'斩马刀','キルソード':'必杀剑','フリッサ':'弗莉萨剑','サンダーソード':'雷电剑','清めの剣':'净化剑','ダ・ミナの剣':'达米纳之剑','毒の剣':'毒剑','グレートソード':'巨剑','疾風の剣':'疾风剑','銀の剣':'银剑',
'木製の槍':'木枪','青銅の槍':'青铜枪','鉄の槍':'铁枪','手槍':'投枪','ショートスピア':'短枪','ハルバード':'斧枪','偃月刀':'偃月刀','ゲキ':'戟','ダ・ミナの槍':'达米纳之枪','ナイトキラー':'骑士杀手','スレンドスピア':'细身枪','グレイブ':'长柄刀','銀の槍':'银枪',
'木製の斧':'木斧','青銅の斧':'青铜斧','鉄の斧':'铁斧','手斧':'手斧','ショートアクス':'短斧','ハンマー':'战锤','ダ・ミナの斧':'达米纳之斧','シールドアクス':'盾斧','バルディッシュ':'长柄斧','スマッシュアクス':'粉碎斧','鷹爪斧':'鹰爪斧','サガリス':'萨加里斯斧','銀の斧':'银斧',
'木製の弓':'木弓','青銅の弓':'青铜弓','鉄の弓':'铁弓','獣狩りの弓':'猎兽弓','ロングボウ':'长弓','馬殺しの弓':'杀马弓','風の弓':'风之弓','毒の弓':'毒弓','ダ・ミナの弓':'达米纳之弓','バトルボウ':'战斗弓','銀の弓':'银弓',
'木製の籠手':'木拳套','青銅の籠手':'青铜拳套','鉄の籠手':'铁拳套','ダ・ミナの籠手':'达米纳拳套','反撃の籠手':'反击拳套','乾坤圏':'乾坤圈','対魔の鉄甲':'对魔铁甲','ジャマダハル':'拳剑','身躱しの籠手':'闪避拳套','銀の籠手':'银拳套'}
NOTE = {'斬馬刀':'克骑','フリッサ':'克甲','清めの剣':'克不死','グレートソード':'克甲','ナイトキラー':'克骑','ハンマー':'克甲','バルディッシュ':'克骑','獣狩りの弓':'克兽','馬殺しの弓':'克骑','キルソード':'高必杀','ダ・ミナの剣':'命中+10','ダ・ミナの槍':'命中+10','ダ・ミナの斧':'命中+10','ダ・ミナの弓':'命中+10','ダ・ミナの籠手':'命中+10','風の弓':'回避+10','疾風の剣':'回避+10','身躱しの籠手':'回避+10','反撃の籠手':'敌方回合反击攻+5','乾坤圏':'射程1-2','対魔の鉄甲':'魔防+3','シールドアクス':'战斗中防守+3','スマッシュアクス':'附带战技','ハルバード':'按斧技能算'}
T = {
'帝都ダグシオン-武器屋':('帝都达格席翁 · 武器屋','Dagsion'),
'カリアネイラの港':('卡利亚涅拉港','Callianeira Port'),
'レギアの町':('雷吉亚镇','Regia'),
'オシリスの村':('欧西利斯村','Osiris'),
'フィーナの漁村':('菲娜渔村','Fina'),
'ザスタの集落':('扎斯塔聚落','Zoste'),
'王都グラン・アラゴン':('王都格兰阿拉贡','Grand Aragon'),
'ウィリー村':('维利村','Whill'),
'海都アレクトー':('海都阿莱克托','Alecto'),
'王都ブレストン':('王都布雷斯顿','Breston'),
'黒煙の谷ダ・ミナ':('黑烟之谷达米纳','Da Mina'),
'キラの村':('基拉村',''),
'アギーニョ村':('阿吉尼奥村','Aguiño'),
'領都カッシート':('领都卡西特','Kassite'),
'パンドラの港町':('潘多拉港','Port of Pandora'),
'王都メガエラ':('王都梅盖拉','Megaira'),
'ジーマの港':('吉玛港',''),
'ライ・オーの港':('莱欧港','Raivo Port'),
'ベネトナシュの村':('贝奈特纳什村','Benetnasch'),
'トバリンの村':('托巴林村','Twalinn'),
'マオン城郭':('马翁城郭','Mahon Castle Town'),
'ヤーマン村':('雅曼村','Yaaman'),
'リベイラ村':('里贝拉村','Ribeira'),
'オレンスの町':('奥伦斯镇','Orens'),
'デモニクの村':('戴蒙村','Daimōn'),
'ニーザの港':('尼萨港','Niiza Port'),
'城塞都市モンス':('城塞都市蒙斯','Mons'),
'バルスク宿場町':('巴尔斯克驿站镇','Barsk Post Town'),
}
TYPE = {'剣':'剑','槍':'枪','斧':'斧','弓':'弓','籠手':'拳套'}
towns = {}; barter=[]
def add(jt, row):
    cn,en = T[jt]
    towns.setdefault(jt, {'cn':cn,'en':en,'jp':jt,'items':[]})['items'].append(row)
csvrows=[]
for line in open('weapons.tsv',encoding='utf-8'):
    n,t,shop,price,stock = line.rstrip('\n').split('\t')
    if 'ヴァンダル' in shop:
        barter.append({'cn':W[n],'jp':n,'type':TYPE[t],'cost':price,'note':NOTE.get(n,'')})
        csvrows.append(['帝都达格席翁 · 范达尔商会','Dagsion',TYPE[t],W[n],n,'以物易物：'+price,'',NOTE.get(n,''),'AppMedia'])
        continue
    p = price.replace('G','')
    row={'cat':TYPE[t],'cn':W[n],'jp':n,'price':int(p),'stock':stock,'note':NOTE.get(n,''),'src':'AppMedia'}
    add(shop,row)
    csvrows.append([T[shop][0],T[shop][1],TYPE[t],W[n],n,p,stock,NOTE.get(n,''),'AppMedia'])
# non-weapon items (allthings.how / altema / GameWith / game8)
extra = [
 ('城塞都市モンス','盾','达米纳之盾','Da Mina Shield',4000,'','守备+4','allthings'),
 ('城塞都市モンス','盾','银盾','Silver Shield',10000,'','守备+6','allthings'),
 ('パンドラの港町','教本','黑魔法教本','Black-Magic Manual',350,'2','每章 10 本（原文）','allthings'),
 ('パンドラの港町','教本','白魔法教本','White-Magic Manual',350,'2','','allthings'),
 ('マオン城郭','教本','黑魔法教本','Black-Magic Manual',350,'3','','allthings'),
 ('マオン城郭','教本','白魔法教本','White-Magic Manual',350,'3','','allthings'),
 ('バルスク宿場町','教本','黑魔法教本','Black-Magic Manual',350,'5','','allthings'),
 ('バルスク宿場町','教本','白魔法教本','White-Magic Manual',350,'5','','allthings'),
 ('カリアネイラの港','教本','飞行教本','Flying Manual',None,'','价格未写','allthings'),
 ('カリアネイラの港','教本','战术教本','Tactics Manual',350,'','别的店 700','allthings'),
 ('王都メガエラ','手形','上级试验手形','上級試験手形',3000,'1','allthings 写 2100','game8'),
 ('王都メガエラ','道具','萨拉米尼亚点心','Saraminian Sweets',70,'无限','支援用','allthings'),
 ('王都メガエラ','箱','良质武具箱','良質な武具箱',800,'','道具屋，可存档读档刷内容','GameWith'),
 ('領都カッシート','箱','质朴武具箱','質素な武具箱',300,'','可存档读档刷内容','altema'),
 ('ライ・オーの港','箱','质朴武具箱','Simple Weapon Crate',None,'','价格未写','raiderking'),
]
for jt,cat,cn,jp,price,stock,note,src in extra:
    add(jt,{'cat':cat,'cn':cn,'jp':jp,'price':price,'stock':stock,'note':note,'src':src})
    csvrows.append([T[jt][0],T[jt][1],cat,cn,jp,price if price else '',stock,note,src])
# Dagsion special
dag_special=[
 {'cat':'手形','cn':'上级试验手形','jp':'上級試験手形','price':3000,'stock':'少量','note':'铜像前手形贩卖员；名声 8 起卖，每章补货','src':'GameWith / k1persia'},
 {'cat':'道具','cn':'伤药','jp':'傷薬','price':300,'stock':'','note':'帝都等 12 处道具屋','src':'GameWith'},
 {'cat':'道具','cn':'调合药','jp':'調合薬','price':800,'stock':'','note':'道具屋','src':'GameWith'},
 {'cat':'道具','cn':'解毒药','jp':'毒消し','price':400,'stock':'','note':'','src':'GameWith'},
 {'cat':'道具','cn':'特效药','jp':'特効薬','price':3000,'stock':'','note':'','src':'GameWith'},
]
towns['帝都ダグシオン-武器屋']['items'] += dag_special
towns['帝都ダグシオン-武器屋']['cn']='帝都达格席翁'
for r in dag_special: csvrows.append(['帝都达格席翁','Dagsion',r['cat'],r['cn'],r['jp'],r['price'],r['stock'],r['note'],r['src']])
vandal_rings=[{'cn':'巨人戒指','jp':"Giant's Ring",'type':'戒指','cost':'Paradise Fish ×1（阿莱克托的范达尔商会）','note':'体格+4，回避-20'},
              {'cn':'疾风戒指','jp':'Gale Ring','type':'戒指','cost':'Dreamtracer ×1（阿莱克托的范达尔商会）','note':'速度+3；梦之标只有坐船才能钓到，迪托利希线大概换不到'}]
barter += vandal_rings
order = sorted(towns.values(), key=lambda t:(t['jp']!='帝都ダグシオン-武器屋', -len(t['items'])))
json.dump({'towns':order,'barter':barter}, open('data.json','w',encoding='utf-8'), ensure_ascii=False)
with open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'shops.csv'),'w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f); w.writerow(['城镇','英文名','类别','物品','原名','价格G','库存','备注','来源']); w.writerows(csvrows)
print(len(order), sum(len(t['items']) for t in order), len(barter))
