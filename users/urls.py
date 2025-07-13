# 进行user 自应用的视图路由
from django.urls import path
from users.views import RegisterView, ImageCodeView, SmsCodeView, LoginView, LogoutView,ForgetPasswordView,UserCenterView,WriteBlogView

from . import views

urlpatterns = [
    # path的第一个参数：路由
    # path的第二个参数：视图函数名

    # 注册功能
    path('register/', RegisterView.as_view(), name='register'),
    # 图片验证码
    path('imagecode/', ImageCodeView.as_view(), name='imagecode'),
    # 短信验证码
    path('smscode/', SmsCodeView.as_view(), name='smscode'),
    # 登陆路由
    path('login/', LoginView.as_view(), name='login'),
    # 退出路由
    path('logout/', LogoutView.as_view(), name='logout'),
    # 忘记密码
    path('forgetpassword/', ForgetPasswordView.as_view(),name='forgetpassword'),
    # 用户中心
    path('center/', UserCenterView.as_view(),name='center'),
    # 写博客路由
    path('writeblog/', WriteBlogView.as_view(),name='writeblog'),
]
