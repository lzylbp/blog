import pymysql

pymysql.install_as_MySQLdb()

# 欺骗 Django 的版本检查
pymysql.version_info = (1, 4, 3, "final", 0)
