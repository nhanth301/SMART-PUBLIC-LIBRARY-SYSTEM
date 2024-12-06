from django.urls import path
from .views import BooksListView, index, BooksAPIView, BookDetailView, navbar, search, tags, tags_view, handle_click
from .views import register, loginUser, logoutUser
from .chatbot_logic import get_book_suggestions

urlpatterns = [
    #path('books/', BooksListView.as_view(), name ='Books'),
    path('', index, name='index'),
    path('api/books/', BooksAPIView.as_view(), name='books-api'),
    path('api/books/<int:book_id>/', BooksAPIView.as_view(), name='book_api-id'),
    #path('books/<int:pk>/', BookDetailView.as_view(), name='book_detail'),
    path('get_book_suggestions/', get_book_suggestions, name='get_book_suggestions'),
    path('search/', search, name='search'),
    #path('navbar/', navbar, name='navbar'),
    path('register', register, name ="register"),
    path('login', loginUser, name ="login"),
    path('logout', logoutUser, name ="logout"),
    path('tags', tags, name ="tags"),
    path('api/tags', tags_view, name='tags_view'),
    path('api/handle_click/', handle_click, name='handle_click')
]