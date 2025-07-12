from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from libs.captcha.captcha import captcha
from django_redis import get_redis_connection

# Create your views here.


from django.views import View


# 注册视图
class RegisterView(View):
    def get(self, requset):
        return render(requset, 'register.html')


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
