from django.db import models
from django.utils import timezone
# Create your models here.

class ArticleCategory(models.Model):
    """
    文章分类
    """
    # 分类标题
    title = models.CharField(max_length=100, blank=True)
    # 分类的创建时间
    created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

    # admin站点显示，调试查看对象方便
    class Meta:
        db_table='tb_category'  # 修改表名
        verbose_name = '类别管理' # admin站点显示
        verbose_name_plural = verbose_name