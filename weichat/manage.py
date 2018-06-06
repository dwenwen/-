from flask import Flask,render_template,request,session,jsonify
import requests
import json
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urlencode
app= Flask(__name__)
app.debug = True
app.secret_key = 'fadfga'

def xml_parser(text):
    dic = {}
    soup = BeautifulSoup(text, 'html.parser')
    div = soup.find(name='error')
    for item in div.find_all(recursive=False):
        dic[item.name] = item.text
    return dic


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'GET':
        ctime = str(int(time.time()*1000))
        # 拼接微信的url
        url = "https://login.wx.qq.com/jslogin?appid=wx782c26e4c19acffb&redirect_uri=https%3A%2F%2Fwx.qq.com%2Fcgi-bin%2Fmmwebwx-bin%2Fwebwxnewloginpage&fun=new&lang=zh_CN&_=(0)".format(ctime)
        # 向微信的url发送get请求
        res = requests.get(url)
        req_code = re.findall('uuid = "(.*)";',res.text)[0]
        session['req_code'] = req_code
        return render_template('login.html',req_code=req_code)


    else:
        pass

@app.route('/pend')
def pend():
    response = {'code': 408}    #给返回一个字典,方便后面处理数据
    req_code=session.get('req_code')
    ctime = str(int(time.time() * 1000))
    url_pend ="https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?loginicon=true&uuid={0}&tip=0&r=-1056783697&_={1}".format(req_code,ctime)
    pend_obj=requests.get(url_pend,'html.parser')
    # print(pend_obj.text)
    if "code=201" in pend_obj.text:
        src = re.findall("userAvatar = '(.*)';", pend_obj.text)[0]
        response['code'] = 201
        response['src'] = src
    elif 'code=200' in pend_obj.text:   #确认登录
        # 确认登录后返回值中返回了一个url,登录成功之后应该会往这个地址跳转
        url_ensure = re.findall('redirect_uri="(.*)";',pend_obj.text)[0]

        # 登录成功之后往这个页面发送请求,
        success_url = url_ensure+'&fun=new&version=v2&lang=zh_CN'
        requ = requests.get(success_url,'html.parser')
        # 响应信息是xml字符串  将数据进行处理,转换成为字典的形式写入到session中
        ticket_dict = xml_parser(requ.text)
        session['ticket_dict'] = ticket_dict
        response['code'] = 200
        session['req_cookie'] = requ.cookies.get_dict()

        
    return jsonify(response)


@app.route('/index')
def index():
    '''
    跳转到网站首页之后,先是发送了一个post请求,进行数据的初始化
    :return:
    '''

    ticket_dict = session.get('ticket_dict')
    init_url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxinit?r=-1131415407&lang=zh_CN&pass_ticket={0}'.format(ticket_dict.get('pass_ticket'))
    
    data_dict = {
        "BaseRequest": {
            "DeviceID": 'e192158401116293',
            "Sid": ticket_dict.get('wxsid'),
            "Uin": ticket_dict.get('wxuin'),
            "Skey": ticket_dict.get('skey'),
        }
    }
    init_ret = requests.post(
        url=init_url,
        json=data_dict  #默认是已经加上请求头了,如果是写的data=data_dict,还要写上请求头headers={'Content-Type':'application/json'}
    )
    init_ret.encoding = 'utf-8'
    user_dict = init_ret.json()     #将post请求的返回值.json相当于是执行了json.loads(init_ret)
    session['current_user']=user_dict['User']
    # print(user_dict['ContactList'])
    print(user_dict)
    return render_template('index.html', user_dict=user_dict)

#获取最近联系人头像地址的过滤器
def get_avata(params):
    # print(params)
    return urlencode({'url':params})
app.add_template_filter(get_avata,'get_avata')

@app.route('/get_img')
def get_img():
    current_user=session.get('current_user')
    req_cookie = session.get('req_cookie')

    url = request.args.get('url')   #获取url中的参数也就是联系人头像的地址

    if url.startswith("/"):
        url = "https://wx2.qq.com" + url
    # url = "https://wx2.qq.com" + current_user['HeadImgUrl']
    ret = requests.get(
        url = url,
        cookies=req_cookie,
        headers={
            'Content-Type':'img/jpeg',
            'Accept':'image/webp,image/apng,image/*,*/*;q=0.8',
           'Host':'wx2.qq.com',
            'Referer': 'https://wx2.qq.com/?&lang = zh_CN',
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.117 Safari/537.36'
        }
    )

    return ret.content

# 获取所有的联系人列表

@app.route('/user_list')
def user_list():
    ctime = int(time.time()*1000)
    ticket_dict = session.get('ticket_dict')
    req_cookie = session.get('req_cookie')
    skey=ticket_dict.get('skey')
    url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?lang=zh_CN&pass_ticket=GNQNuXUhpMpNtpx0YO9ogxssyHaRekQQ0ZjjiqkoM8gYEap7vjbotV3YGCxrs2Fm&r={0}&seq=0&skey={1}'.format(ctime,skey)

    ret = requests.get(url,cookies=req_cookie)
    ret.encoding = 'utf-8'      #请求返回的数据进行解码
    user_lists = ret.json()     #进行反序列化
    print(user_lists)
    return render_template('user_list.html',user_lists=user_lists)

@app.route('/send_message',methods=['GET','POST'])
def send_message():
    if request.method == 'GET':
        return render_template('send.html')

    ctime = str(time.time()*1000)
    current_user=session.get('current_user')
    from_user = current_user.get('UserName')    #发送人
    to =request.args.get('to_username')  #给谁发送

    content = request.form.get('content')   #发送内容

    ticket_dict = session.get('ticket_dict')
    pass_ticket = ticket_dict.get('pass_ticket')

    url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg?lang=zh_CN&pass_ticket={0}'.format(pass_ticket)

    data_dict = {
        "BaseRequest": {
            "DeviceID": 'e192158401116293',
            "Sid": ticket_dict.get('wxsid'),
            "Uin": ticket_dict.get('wxuin'),
            "Skey": ticket_dict.get('skey'),
        },
        "Msg":{
            "ClientMsgId":ctime,
            "LocalID":ctime,
            "FromUserName":from_user,
            # "ToUserName":to,@fb73bba7d1f40ef316196b8e251eaa1f1737d19fc4620bfaf8d948549286ae4d
            "ToUserName":'@f56732095a8cdbffeb7fbb5394ee6b69c94e521a94cc0657a7cfe28d5c3cb154',
            # "Content":content,
            "Content":'爱你呦',
            "Type":1
        },
        "Scene":0

    }

    ret = requests.post(
        url=url,
        data=bytes(json.dumps(data_dict,ensure_ascii=False),encoding='utf-8')   #源码中使用的是Latin-1的编码,requests发送的是socket,在变成字节的时候出错了,所以再将它变成字节
    )
    print(ret.text)

    return 'ok'



if __name__ == '__main__':
    app.run()
