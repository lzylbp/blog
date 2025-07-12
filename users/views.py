from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse
from libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from django.shortcuts import render
import logging

logger = logging.getLogger('django')
from django.views import View
from utils.response_code import RETCODE
from random import randint
from libs.yuntongxun.sms import CCP


# Create your views here.

import re
from users.models import User
from django.db import DatabaseError

# 注册视图
class RegisterView(View):
    def get(self, requset):
        """"""
        return render(requset, 'register.html')

    def post(self,request):
        """"""
        """
        1.接收数据
        2.验证数据
            2.1参数是否齐全
            2.2手机号的格式是否正确
            2.3密码是否符合格式
            2.4密码和确认密码要一致
            2.5短信验证码是否edis中的一致
        3.保存注册信息
        4.返回响应跳转到指定页面
        """
        # 1.接收数据
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode=request.POST.get('sms_code')
        # 2.验证数据
        #     2.1参数是否齐全
        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest('缺少必传参数')
        #     2.2手机号的格式是否正确
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('请输入正确的手机号码')
        #     2.3密码是否符合格式
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest('请输入8-20位的密码')
        #     2.4密码和确认密码要一致
        if password != password2:
            return HttpResponseBadRequest('两次输入的密码不一致')
        #     2.5短信验证码是否edis中的一致
        redis_conn = get_redis_connection('default')
        sms_code_server = redis_conn.get('sms:%s' % mobile)
        if sms_code_server is None:
            return HttpResponseBadRequest('短信验证码已过期')
        if smscode != sms_code_server.decode():
            return HttpResponseBadRequest('短信验证码错误')
        # 3.保存注册信息
        # create_user可以使用系统的方法来对密码进行伽密
        try:
            user = User.objects.create_user(username=mobile,
                                            mobile=mobile,
                                            password=password
                                            )
        except DatabaseError:
            return HttpResponseBadRequest('注册失败')
        # 4.返回响应跳转到指定页面
        # 暂时返回一个注册成功的信息，后期再实现跳转到指定页面
        return HttpResponse('注册成功，重定向到首页')


class ImageCodeView(View):

    def get(self, request):
        """
        1.接收前端传递过来的uuid
        2.判断uuid是否获取到
        3.通过调用captcha来生成图片验证码(图片二进制和图片内容)
        4.将图片验内容保存到redis中，并设置过期时间
            uuid作为一个key,图片内容作为一个value
            同时我们还需要设置一个时效
        5.返回图片二进制
        """
        # 1.获取前端传递过来的参数
        uuid = request.GET.get('uuid')
        # 2.判断uuid是否获取到
        if uuid is None:
            return HttpResponseBadRequest('参数错误，没有传递uuid')
        # 3.通过调用 captcha 来生成图片验证码(图片二进制和图片内容)
        text, image = captcha.generate_captcha()
        # 4.将图片验内容保存到redis中，并设置过期时间
        redis_conn = get_redis_connection('default')
        # key 设置为uuid
        # seconds  过期秒数 300秒 5分钟过期时间
        # value text
        redis_conn.setex('img:%s' % uuid, 300, text)
        # 5.返回图片二进制，将生成的图片以content_type为image/jpeg的形式返回给请求
        return HttpResponse(image, content_type='image/jpeg')


class SmsCodeView(View):

    def get(self, request):

        """
        http://127.0.0.1:8000/smscode/?mobile=18888888888&_code=xxxx&uuid=xxxxx
        1.接收参数
        2.参数的验证
            2.1验证参数是否齐全
            2.2图片验证码的验证
                    连接redis,获取redis中的图片验证码
                    判断图片验证码是否存在
                    如果图片验证码末过期，我们获取到之后就可以删除图片验证码
                    对比图片验证码
        3.生成短信验证码
        4.保存短信验证码到redis中
        5.发送短信
        6.返回响应
        """
        # 1.接收参数（查询字符串的形式）
        mobile = request.GET.get('mobile')
        image_code_client = request.GET.get('image_code')
        uuid = request.GET.get('uuid')

        # 2.参数的验证
        #   2.1验证参数是否齐全
        if not all([image_code_client, uuid, mobile]):
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '缺少必传参数'})

        #   2.2图片验证码的验证
        #       连接redis, 获取redis中的图片验证码
        redis_conn = get_redis_connection('default')
        image_code_server = redis_conn.get('img:%s' % uuid)
        #       判断图片验证码是否存在（图形验证码过期或者不存在）
        if image_code_server is None:
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图形验证码失效'})
        #      如果图片验证码末过期，我们获取到之后就可以删除图片验证码
        try:
            redis_conn.delete('img:%s' % uuid)
        except Exception as e:
            logger.error(e)
        #       对比图形验证码,注意大小写的问题，redis数据类型是：bytes类型
        image_code_server = image_code_server.decode()  # bytes转字符串
        if image_code_client.lower() != image_code_server.lower():  # 转小写后比较
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '输入图形验证码有误'})

        # 3.生成短信验证码：生成6位数验证码
        sms_code = '%06d' % randint(0, 999999)
        # 为了后期比对方便，我们可以将短信验证码记录到日志中
        logger.info(sms_code)
        # 4.保存短信验证码到redis中，并设置有效期
        redis_conn.setex('sms:%s' % mobile, 300, sms_code)
        # 5.发送短信验证码
        # 参数1：测试手机号
        # 参数2：模板内容列表：1}短信验证码 2}分钟有效
        # 参数3：模板免费开发测试使用的模板ID为1
        # CCP().send_template_sms(mobile, [sms_code, 5], 1)

        # 6.响应结果
        return JsonResponse({'code': RETCODE.OK, 'errmsg': '发送短信成功', 'sms_code': sms_code})
