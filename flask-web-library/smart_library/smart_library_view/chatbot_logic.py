from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import Books
from pgvector.django import CosineDistance

from django.db.models import F, Q
import requests
import math

api_model = 'https://zep.hcmute.fit/7561/transform'

def encode_message(message):
    data = {
        'texts': [message]
    }
    try:
        response = requests.post(api_model, json=data)
        
        # Kiểm tra nếu yêu cầu thành công
        if response.status_code == 200:
            embeddings = response.json().get('embeddings', [])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]  
            else:
                print('Không tìm thấy embedding trong kết quả trả về.')
        else:
            print(f'Yêu cầu thất bại với mã trạng thái: {response.status_code}')
            print('Thông điệp trả về:', response.text)
    
    except requests.exceptions.RequestException as e:
        print('Lỗi khi kết nối đến API:', e)
    
    return None


@csrf_exempt
def get_book_suggestions(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message', '')
        message_embedding = encode_message(message)
        top_n = 5 

        if message_embedding is None:
            return JsonResponse({'error': 'Invalid message embedding'}, status=400)
        
        # Tìm kiếm sách tương đồng với message
        similar_books = Books.objects.annotate(
            summary_similarity=CosineDistance(F('summary_embed'), message_embedding),
            title_similarity=CosineDistance(F('title_embed'), message_embedding)
        ).order_by('title_similarity', 'summary_similarity')[:top_n]

        print(similar_books)


        # suggestions = [ 
        #     {
        #         'id': book.id,
        #         'title': book.title,
        #         'summary': book.summary,
        #         'summary_similarity': book.summary_similarity,
        #         'title_similarity': book.title_similarity, 
        #     } for book in similar_books
        # ]

        suggestions = []

        for book in similar_books:
            summary = book.summary if book.summary != 'NaN' else 'No summary available'
            summary_similarity = (
                book.summary_similarity 
                if book.summary_similarity is not None and not math.isnan(book.summary_similarity) 
                else 'No summary available'
            )

            title_similarity = (
                book.title_similarity 
                if book.title_similarity is not None and not math.isnan(book.title_similarity) 
                else 'No title available'
            )
            
            suggestions.append({
                'id': book.id,
                'title': book.title,
                'summary': summary,
                'summary_similarity': summary_similarity,
                'title_similarity': title_similarity, 
            })

        # Trả về danh sách sách tương đồng và message ban đầu
        response_data = {
            'message': message,
            'suggestions': suggestions,
        }

        return JsonResponse(response_data, safe=False)
    return JsonResponse({'error': 'Invalid request method'}, status=400)