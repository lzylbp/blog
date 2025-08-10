from django.shortcuts import render
from django.views import View
from home.models import ArticleCategory
from django.http import HttpResponseNotFound
# Create your views here.

class IndexView(View):
    """
    首页广告
    1.获取所有分类信息
    2.接收用户点击的分类id
    3.根据分类id进行分类的查询
    4.组织数据传递给模板
    """
    def get(self, request):
        """提供首页广告界面"""
        # 1.获所有分类信息
        categories = ArticleCategory.objects.all()
        # 2.接收用户点击的分类id
        # ?cat_id=xxx&page_num=xxx&page_size=xxx
        cat_id = request.GET.get('cat_id', 1)
        # 3.根据分类1d进行分类的查诡
        try:
            category = ArticleCategory.objects.get(id=cat_id)
        except ArticleCategory.DoesNotExist:
            return HttpResponseNotFound('没有此分类')
        # 4.组织数据传递给模板
        context = {
            'categories':categories,
            'category':category
        }
        # return render(request, 'index.html')
        return render(request, 'index.html', context=context)