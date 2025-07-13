from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse

from libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from django.shortcuts import render

from django.views import View
from utils.response_code import RETCODE
from random import randint
from libs.yuntongxun.sms import CCP

# Create your views here.

import re
from users.models import User
from django.db import DatabaseError
from django.shortcuts import redirect
from django.urls import reverse


# 注册视图
class RegisterView(View):
    def get(self, requset):
        """"""
        return render(requset, 'register.html')

    def post(self, request):
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
        smscode = request.POST.get('sms_code')
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

        #   状态保持
        from django.contrib.auth import login
        login(request, user)

        # 4.返回响应跳转到指定页面
        # 暂时返回一个注册成功的信息，后期再实现跳转到指定页面
        # return HttpResponse('注册成功，重定向到首页')

        # redirect是进行重定向
        # reverse是可以通过 namespace：name来获取到视图所对应的路由
        # redirect
        # return redirect(reverse('home:index'))

        # 跳转到首页
        response = redirect(reverse('home:index'))
        # #设置cooki信息，以方便首页中用户信息展示的判断和用户信息的展示
        response.set_cookie('is_login', True)
        response.set_cookie('username', user.username, max_age=30 * 24 * 3600)

        return response


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


import logging

logger = logging.getLogger('django')


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


class LoginView(View):
    def get(self, request):

        return render(request, 'login.html')

    def post(self, request):
        """
        1.接收参数
        2.参数的验证
            2.1 验证手机号是否符合
            2.2  验证密码是否符合规则
        3.用户认证登录
        4.状态的保持
        5.根据用户选择的是否记住登录状态来进行判断
        6.为了首页显示我们需要设置一些cookie信息
        7。返回啊应
        """
        # 1.接收参数
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        # 2.参数的验证
        if not all([mobile, password]):
            return HttpResponseBadRequest('缺少必传参数')
        #     2.1 验证手机号是否符合
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('请输入正确的手机号')
        #     2.2  验证密码是否符合规则
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest('密码最少8位，最长20位')
        # 3.用户认证登录
        # 采用系统自带的认证方法进行认证
        # 如果我们的用户名和密码正确，会返回:user
        # 如果我们的用户名或密码不正确，会返回:None
        from django.contrib.auth import authenticate
        # 默认的认证方法是针对于username字段进行用户名的判断
        # 当前的判断信息是手机号，所以我们需要修改一下认证字段
        # 我们需要到User模型中进行修改，等测试出现问题的时候，我们再修改
        user = authenticate(mobile=mobile, password=password)

        if user is None:
            return HttpResponseBadRequest('用户名或密码错误')

        # 4.状态的保持
        from django.contrib.auth import login
        login(request, user)
        # 5.根据用户选择的是否记住登录状态来进行判断
        # 6.为了首页显示我们需要设置一些cookie信息

        # 根据next参数来进行页面的跳转
        next_page = request.GET.get('next')
        if next_page:
            response = redirect(next_page)
        else:
            response = redirect(reverse('home:index'))

        # response = redirect(reverse('home:index'))
        if remember != 'on':
            # 没有记住用户：浏览器会话结束就过期
            request.session.set_expiry(0)
            # 设置cookie
            response.set_cookie('is_login', True)
            response.set_cookie('username', user.username, max_age=30 * 24 * 3600)
        else:
            # 记住用户：None表示两周后过期
            request.session.set_expiry(None)
            # 设置cookie
            response.set_cookie('is_login', True, max_age=14 * 24 * 3600)
            response.set_cookie('username', user.username, max_age=30 * 24 * 3600)

        # 7.返回啊应
        return response


from django.contrib.auth import logout


class LogoutView(View):
    def get(self, request):
        # 1.session数据清除
        logout(request)
        # 2.删除部分cookie数据
        response = redirect(reverse('home:index'))
        response.delete_cookie('is_login')
        # 3.跳转到首页
        return response


class ForgetPasswordView(View):

    def get(self, request):
        return render(request, 'forget_password.html')

    def post(self, request):
        """
        1.接收数据
        2.验证数据
            2.1判断参数是否齐全
            2.2手机号是否符合格则
            2.3判断密码是否符合格则
            2.4判晰确认密码和密码是否一致
            2.5判断短信验证码是否正确
        3.根据手机号进行用户信息的查询
        4.如果手机号查询出用户信息则进行用户密码的修改
        5.如果手机号没有查询出用户信息，则进行新用户的创建
        6.进行页面跳转，跳转到登录页面
        7.返回响应
        """
        # 1.接收数据
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode = request.POST.get('sms_code')

        # 2.验证数据
        # 2.1判断参数是否齐全
        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest('缺少必传参数')

        # 2.2手机号是否符合格则
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('请输入正确的手机号码')

        # 2.3判断密码是否符合格则 8-20个数字
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest('请输入8-20位的密码')

        # 2.4判晰确认密码和密码是否一致
        if password != password2:
            return HttpResponseBadRequest('两次输入的密码不一致')

        # 2.5判断短信验证码是否正确
        redis_conn = get_redis_connection('default')
        sms_code_server = redis_conn.get('sms:%s' % mobile)
        if sms_code_server is None:
            return HttpResponseBadRequest('短信验证码已过期')
        if smscode != sms_code_server.decode():
            return HttpResponseBadRequest('短信验证码错误')

        # 3.根据手机号进行用户信息的查询
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            # 5.如果手机号没有查询出用户信息，则进行新用户的创建
            try:
                User.objects.create_user(username=mobile,
                                         mobile=mobile,
                                         password=password
                                         )
            except Exception:
                return HttpResponseBadRequest('修改失败，请稍后再试')
        else:
            # 4.如果手机号查询出用户信息则进行用户密码的修改
            user.set_password(password)
            user.save()

        # 6.进行页面跳转，跳转到登录页面
        response = redirect(reverse('users:login'))
        # 7.返回响应
        return response


from django.contrib.auth.mixins import LoginRequiredMixin


# LoginRequiredMixin
# 如果用户未登录的话，则会进行默认的跳转
# 默认的跳转连接是：accounts/login/?next=xxx
class UserCenterView(LoginRequiredMixin, View):

    def get(self, request):
        # 获取登陆用户信息
        user = request.user
        # 组织获取用户的信息
        context = {
            'username': user.username,
            'mobile': user.mobile,
            'avatar': user.avatar.url if user.avatar else None,
            'user_desc': user.user_desc
        }
        return render(request, 'center.html', context=context)

    def post(self, request):
        """
        1.接收参数
        2.将参数保存起来
        3.更新cookie中的username信，息
        4.刷新当前页面（重定向操作）
        5.返回响应
        """

        # 1.接收参数
        # 2.将参数保存起来
        # 3.更新cookie中的username信息
        # 4.刷新当前页面（重定向操作）


        # 1.接收参数
        user = request.user
        username = request.POST.get('username', user.username)
        user_desc = request.POST.get('desc', user.user_desc)
        avatar = request.FILES.get('avatar')

        # 2.将参数保存起来
        try:
            user.username = username
            user.user_desc = user_desc
            if avatar:
                user.avatar = avatar
            user.save()
        except Exception as e:
            logger.error(e)
            return HttpResponseBadRequest('更新失败，请稍后再试')

        # 3.更新cookie中的username信息
        # 4.刷新当前页面（重定向操作）
        response = redirect(reverse('users:center'))
        response.set_cookie('username', user.username, max_age=30 * 24 * 3600)
        # 5.返回响应
        return response

from home.models import ArticleCategory
class WriteBlogView(LoginRequiredMixin,View):

    def get(self,request):
        # 查询所有分类模型
        categories = ArticleCategory.objects.all()
        context = {
            'categories': categories
        }
        return render(request,'write_blog.html',context)



