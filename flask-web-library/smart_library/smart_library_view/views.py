from django.shortcuts import render
from django.views.generic import ListView, DetailView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Books
from .serializers import BooksSerializer


# Create your views here.
class BooksListView(ListView):
    model = Books
    template_name = 'books.html'  
    context_object_name = 'books'  

    def get_queryset(self):
        return Books.objects.all()
    
    
class BooksAPIView(APIView):
    def get(self, request, format=None):
        books = Books.objects.all()
        serializer = BooksSerializer(books, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class BookDetailView(DetailView):
    model = Books
    template_name = 'book_detail.html'  
    context_object_name = 'book'  

def index(request):
    return render(request, 'index.html')