from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import ListView, DetailView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.postgres.aggregates import StringAgg
from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.urls import reverse


from rest_framework.generics import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Books, BooksTags, Tags
from .serializers import BooksSerializer
from .forms import CreateUserForm
from django.conf import settings
from .chatbot_logic import get_book_suggestions_from_query
from django.views.decorators.csrf import csrf_exempt
import time
import requests
import json
from quixstreams import Application
import ast

app = Application(broker_address="kafka-ct:9092", consumer_group="quix")
sessions_topic = app.topic(name="UserInteraction", value_serializer="json")
producer = app.get_producer()

# Create your views here.
class BooksListView(ListView):
    model = Books
    template_name = 'books.html'  
    context_object_name = 'books'  

    def get_queryset(self):
        return Books.objects.all()
    
    
class BooksAPIView(APIView):
    def get(self, request, book_id=None, format=None):
        if book_id:
            try:
                book = Books.objects.get(id=book_id)  
            except Books.DoesNotExist:
                return Response({"error": "Book not found"}, status=status.HTTP_404_NOT_FOUND)
            book_tags = BooksTags.objects.filter(book_id=book.id)
            tag_names = Tags.objects.filter(id__in=book_tags.values('tag_id'))
            tag_list = [tag.name for tag in tag_names]
            book_data = BooksSerializer(book).data
            book_data['tags'] = tag_list
            book_data['image'] =  f"{settings.MEDIA_URL}{settings.MEDIA_IMAGE_PATH}/{book_data['image']}"
            return Response(book_data, status=status.HTTP_200_OK)
        else:
            books = Books.objects.all()
            response_data = []

            for book in books:
                # Lấy các tag của sách
                book_tags = BooksTags.objects.filter(book_id=book.id)
                tag_names = Tags.objects.filter(id__in=book_tags.values('tag_id'))
                
                # Kết nối các tag thành chuỗi với dấu phẩy
                tag_list = [tag.name for tag in tag_names]

                book_data = BooksSerializer(book).data
                book_data['tags'] = tag_list  
                # book_data['embed_tags'] = embed_tags  

                # Thêm cuốn sách vào danh sách kết quả
                response_data.append(book_data)

        return Response(response_data, status=status.HTTP_200_OK)
        # serializer = BooksSerializer(books, many=True)
        # return Response(serializer.data, status=status.HTTP_200_OK)
    
class BookDetailView(DetailView):
    model = Books
    template_name = 'book_detail.html'  
    context_object_name = 'book'  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # # Kiểm tra nếu có ảnh và nối MEDIA_URL
        # if context['book'].image:
        #     context['book'].image = f"{settings.MEDIA_URL}{settings.MEDIA_IMAGE_PATH}/{context['book'].image}"
        
        return context
    

def get_menu_item():
    menu_items = [
        {"name": "Books", "href": reverse("index")},
        {"name": "Hot Books", "href": "#hot-books"},
        {"name": "Top Rated Books", "href": "#top-rated"},
        {"name": "Read Books", "href": "#read-books"},
        {"name": "Unread Books", "href": "#unread-books"},
        {"name": "Discover", "href": "#discover"},
        {"name": "Tags", "href": reverse("tags")},
        {"name": "Authors", "href": "#authors"},
    ]
    return menu_items

def get_books_with_tags(books):
    books_data = []

    for book in books:
        # Chuyển đổi sách thành dict
        book_data = book.to_dict()

        # Lấy các tag của sách
        book_tags = BooksTags.objects.filter(book_id=book.id)
        tag_names = Tags.objects.filter(id__in=book_tags.values('tag_id'))
        
        # Lấy tên các tag thành một danh sách
        tag_list = [tag.name for tag in tag_names]
        book_data['tags'] = tag_list

        # Thêm thông tin sách vào danh sách
        books_data.append(book_data)

    return books_data

def index(request):
    try:
        response = requests.get("http://fast-api:88/rec/", params={"uid": request.user.id})
        if response.status_code == 200:  
            try:
                list_recommend = response.json()["result"]
            except ValueError:
                list_recommend = [] 
        else:
            list_recommend = []  
    except requests.RequestException as e:
        print(f"Lỗi kết nối API gợi ý: {e}")
        list_recommend = []
    books_recommend = []
    for book_id in list_recommend:
        api_url = f"http://localhost:1111/api/books/{book_id}/"  
        response = requests.get(api_url)
        if response.status_code == 200:
            books_recommend.append(response.json())

    books = Books.objects.all()
    books_data = get_books_with_tags(books)
    
    return render(request, 'home.html', {'books': books_data, 'menu_items': get_menu_item(), 'books_recommend': books_recommend,})

def navbar(request):
    return render(request, 'navbar.html')

def register(request):
    form = CreateUserForm()

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            form.save()

    context = {'form' : form}
    return render(request, 'register.html', context)

def loginUser(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username = username, password = password)
        if user is not None:
            login(request, user)

            # Lưu thông tin user_id vào session
            request.session['user_id'] = user.id
            request.session['username'] = user.username 
            
            # Đặt thời gian hết hạn session (tuỳ chọn)
            request.session.set_expiry(3600) 

            return redirect('index')
        else: messages.info(request, 'Wrong Username or Password!')
    context = {
        'username': request.user.username if request.user.is_authenticated else None
    }
    return render(request, 'login.html', context)

def logoutUser(request):
    logout(request)
    return redirect('login')

def search(request):
    query = request.GET.get('query', '').strip()
    search_type = request.GET.get('search_type', '').strip()

    if search_type == 'content' and query:
        response = get_book_suggestions_from_query(query, top_n=10)
        
        if 'error' in response:
            return JsonResponse({'error': 'Invalid search request'}, status=400)
        
        suggestions = response.get('suggestions', [])
        
        # Trả về sách gợi ý cho người dùng
        return render(request, 'home.html', {'books': suggestions, 'menu_items': get_menu_item(), 'is_searching': True})

    books = Books.objects.all()

    if query and search_type:
        if search_type == 'title':
            books = books.filter(title__icontains=query)
        elif search_type == 'tags':
            tag_ids = Tags.objects.filter(name__icontains=query).values_list('id', flat=True)
            book_ids = BooksTags.objects.filter(tag_id__in=tag_ids).values_list('book_id', flat=True)
            books = books.filter(id__in=book_ids)
        elif search_type == 'author':
            books = books.filter(author__icontains=query)
        elif search_type == 'content':
            pass
    
    books_data = get_books_with_tags(books)
    return render(request, 'home.html', {'books': books_data, 'menu_items': get_menu_item(), 'is_searching': True})

def tags(request):
    tags_data = get_tags_with_books()
    return render(request, 'tags.html', {'tags': tags_data, 'menu_items': get_menu_item()})

def get_tags_with_books():
    tags = Tags.objects.all()

    # Tạo một dictionary để lưu các tag và sách tương ứng
    tags_data = []

    for tag in tags:
        # Lấy các sách tương ứng với tag này
        books = Books.objects.filter(id__in=BooksTags.objects.filter(tag_id=tag.id).values('book_id'))
        
        # Tạo danh sách sách cho mỗi tag
        books_data = get_books_with_tags(books)

        # Thêm tag và sách vào danh sách kết quả
        tags_data.append({
            'name': tag.name,
            'books': books_data
        })
    return tags_data

def tags_view(request):
    # Lấy dữ liệu tag cùng với sách
    tags_data = get_tags_with_books()
    
    # Trả về dữ liệu dưới dạng JSON
    return JsonResponse(tags_data, safe=False)

@csrf_exempt
def handle_click(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        book_id = data.get('book_id')
        action = data.get('action')
        user_id = request.user.id if request.user.is_authenticated else None
        session_id = request.session.session_key
        current_time = int(time.time())

        # Kiểm tra xem có trường nào bị None không
        if not all([book_id, action, user_id, session_id]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        message = {
            'sid': session_id,
            'uid': user_id,
            'bid': book_id,
            'action': action,
            'timestamp': current_time
        }

        # Đẩy dữ liệu vào Kafka
        kafka_msg = sessions_topic.serialize(key=message["sid"], value=message)      
        producer.produce(
            topic=sessions_topic.name,
            key=kafka_msg.key,
            value=kafka_msg.value,
        )
        return JsonResponse({'status': 'Success'}, status=200)

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)

import pandas as pd
import psycopg2
import seaborn as sns
import matplotlib.pyplot as plt
import io
from django.http import HttpResponse

# Make sure these imports are at the top of your file
import base64  # Add this import
from django.shortcuts import render
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import psycopg2
import io

def visualize(request):
    try:
        # Database connection with context manager
        with psycopg2.connect(
            dbname="spls",
            user="admin",
            password="admin",
            host="postgres-ct",
            port="5432"
        ) as conn:
            images = []
            
            # First visualization
            query1 = """
            SELECT 
                recommendation_date, 
                action_type, 
                total_skipped, 
                total_clicked, 
                total_read, 
                total_no_interaction, 
                total_recommended_books, 
                total_recommendations
            FROM vw_recommendation_rate_by_action
            """
            data1 = pd.read_sql_query(query1, conn)
            data1['recommendation_date'] = pd.to_datetime(data1['recommendation_date'])

            plt.figure(figsize=(14, 8))
            sns.barplot(
                data=data1, 
                x="recommendation_date", 
                y="total_recommended_books", 
                hue="action_type"
            )
            plt.title("User Actions on Recommended Books by Date", fontsize=16)
            plt.xlabel("Recommendation Date", fontsize=14)
            plt.ylabel("Total Recommended Books", fontsize=14)
            plt.legend(title="Action Type", loc="upper right")
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            buffer.seek(0)
            image1 = base64.b64encode(buffer.getvalue()).decode()
            images.append(image1)

            # Second visualization
            query2 = """
            SELECT 
                year, 
                quarter, 
                month, 
                actionname, 
                action_count, 
                unique_users, 
                unique_books
            FROM vw_user_interaction_analysis
            """
            data2 = pd.read_sql_query(query2, conn)
            
            data2['month_label'] = data2['year'].astype(str) + "-" + data2['month'].astype(str).str.zfill(2)
            data2['action_per_user'] = data2['action_count'] / data2['unique_users']

            plt.figure(figsize=(14, 8))
            sns.lineplot(
                data=data2,
                x="month_label",
                y="action_per_user",
                hue="actionname",
                marker="o"
            )
            plt.title("Action per User Over Time by Action Type", fontsize=16)
            plt.xlabel("Month", fontsize=14)
            plt.ylabel("Actions per User", fontsize=14)
            plt.legend(title="Action Type", loc="upper right")
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            buffer.seek(0)
            image2 = base64.b64encode(buffer.getvalue()).decode()
            images.append(image2)

            query3 = """
            SELECT weights, timestamp FROM model where type = 'losses' ORDER BY timestamp DESC LIMIT 3;
            """
            data = pd.read_sql_query(query3, conn)
            loss_data = []
            timestamps = []

            for row in data.itertuples():
                loss_values = row.weights  
                loss_data.append(loss_values)
                timestamps.append(row.timestamp)

            # Tạo biểu đồ
            plt.figure(figsize=(10, 6))
            for idx, loss_values in enumerate(loss_data):
                plt.plot(loss_values, label=f"Training {idx + 1} - {timestamps[idx]}")

            plt.title("Loss Values Over 3 Most Recent Training RecSys Rounds")
            plt.xlabel("Epochs")
            plt.ylabel("Loss")
            plt.legend(title="Training Rounds")
            plt.xticks(rotation=45)
            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            buffer.seek(0)
            image3 = base64.b64encode(buffer.getvalue()).decode()
            images.append(image3)
            
            query4 = """
            SELECT weights, timestamp FROM model where type = 'adapter_losses' ORDER BY timestamp DESC LIMIT 3;
            """
            data = pd.read_sql_query(query4, conn)
            loss_data = []
            timestamps = []

            for row in data.itertuples():
                loss_values = row.weights 
                loss_data.append(loss_values)
                timestamps.append(row.timestamp)

            # Tạo biểu đồ
            plt.figure(figsize=(10, 6))
            for idx, loss_values in enumerate(loss_data):
                plt.plot(loss_values, label=f"Training {idx + 1} - {timestamps[idx]}")

            plt.title("Loss Values Most Recent Training Linear Adapter Rounds")
            plt.xlabel("Epochs")
            plt.ylabel("Loss")
            plt.legend(title="Training Rounds")
            plt.xticks(rotation=45)
            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            buffer.seek(0)
            image4 = base64.b64encode(buffer.getvalue()).decode()
            images.append(image4)

        return render(request, 'multiple_charts.html', {'images': images})
        
    except Exception as e:
        # Log the error and return an error page
        print(f"Error occurred: {str(e)}")
        return render(request, 'error.html', {'error_message': str(e)})
