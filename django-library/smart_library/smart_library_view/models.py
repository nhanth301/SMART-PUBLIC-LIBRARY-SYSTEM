# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from pgvector.django import VectorField
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.conf import settings

class Books(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.CharField()
    summary = models.CharField()
    image = models.CharField()
    author = models.CharField()
    published_date = models.DateTimeField()
    created_date = models.DateTimeField()
    modified_date = models.DateTimeField()
    title_embed = VectorField(dimensions=768, blank=True, null=True)
    summary_embed = VectorField(dimensions=768, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'books'

    def to_dict(self):
        image_url = (
            f"{settings.MEDIA_URL}{settings.MEDIA_IMAGE_PATH}/{self.image}"
            if self.image
            else None
        )

        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'image': image_url,
            'author': self.author,
            'published_date': self.published_date,
            'created_date': self.created_date,
            'modified_date': self.modified_date,
        }



class BooksTags(models.Model):
    book_id = models.IntegerField(primary_key=True)  
    tag_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'books_tags'
        unique_together = (('book_id', 'tag_id'),)


class Tags(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField()

    class Meta:
        managed = False
        db_table = 'tags'


# class UserManager(BaseUserManager):
#     pass
#     def _create_user(self, username, email, password=None, **extra_fields):
#         if not email:
#             raise ValueError('The Email field must be set')
#         if not password:
#             raise ValueError('The Password field must be set') 
#         if not username:
#             raise ValueError('The Username field must be set') 
#         email = self.normalize_email(email)
#         user = self.model(username=username, email=email, **extra_fields)
#         user.set_password(password)
#         user.save(using=self._db)
#         return user
    
#     def create_user(self, username, email=None, password = None, **extra_fields):
#         extra_fields.setdefault('is_staff', False)
#         extra_fields.setdefault('is_superuser', False)
#         return self._create_user(username, email, password, **extra_fields)
    
#     def create_staffuser(self, username, email=None, password = None, **extra_fields):
#         extra_fields.setdefault('is_staff', True)
#         extra_fields.setdefault('is_superuser', False)
#         return self._create_user(username, email, password, **extra_fields)

#     def _create_superuser(self, username, email, password=None, **extra_fields):
#         extra_fields.setdefault('is_staff', True)
#         extra_fields.setdefault('is_superuser', True)
#         return self._create_user(username, email, password, **extra_fields)



# class User(AbstractBaseUser):
#     username = models.CharField(max_length=150, unique=True, default='example')
#     email = models.EmailField(max_length=255, unique=True, default='example@example.com')
#     first_name = models.CharField(max_length=30, null=False, default='A')
#     last_name = models.CharField(max_length=30, null=False, default='Nguyen Van')

#     is_active = models.BooleanField(default=True)
#     is_staff = models.BooleanField(default=False)
#     is_superuser = models.BooleanField(default=False)

#     date_joined = models.DateTimeField(default=timezone.now)
#     last_login = models.DateTimeField(blank=True, null=True)

#     objects = UserManager()

#     USERNAME_FIELD = 'username'  
#     EMAIL_FIELD = 'email'
#     REQUIRED_FIELDS = ['email']  

#     class Meta:
#         verbose_name = 'User'
#         verbose_name_plural = 'User'

