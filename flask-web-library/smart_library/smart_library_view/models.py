# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from pgvector.django import VectorField

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
