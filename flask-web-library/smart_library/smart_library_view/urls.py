from django.urls import path
from .views import BooksListView, index, BooksAPIView, BookDetailView
from .chatbot_logic import get_book_suggestions

urlpatterns = [
    # path('api/signup/', views.api_signup, name='api_signup'),
    # path('api/signin/', views.api_signin, name='api_signin'),
    path('books/', BooksListView.as_view(), name ='Books'),
    path('', index, name='index'),
    path('api/books/', BooksAPIView.as_view(), name='books-list'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book_detail'),
    path('get_book_suggestions/', get_book_suggestions, name='get_book_suggestions'),
]