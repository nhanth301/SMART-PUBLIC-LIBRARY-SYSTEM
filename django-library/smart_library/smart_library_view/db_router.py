class DatabaseRouter:
    """
    Điều hướng bảng mặc định của Django vào cơ sở dữ liệu riêng.
    """
    django_apps = [
        'auth',
        'contenttypes',
        'sessions',
        'admin',
        'messages',
    ]

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'smart_library_view' :
            return 'librarydb'
        if model._meta.app_label in self.django_apps:
            return 'default'  
        return 'librarydb'  

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'smart_library_view' :
            return 'librarydb'
        if model._meta.app_label in self.django_apps:
            return 'default'
        return 'librarydb'

    def allow_relation(self, obj1, obj2, **hints):
        # Cho phép quan hệ giữa các bảng trong cùng cơ sở dữ liệu
        db_list = ('default', 'librarydb')
        if obj1._state.db in db_list and obj2._state.db in db_list:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'smart_library_view':
            return db == 'librarydb'
        if app_label in self.django_apps:
            return db == 'default'
        return db == 'librarydb'
