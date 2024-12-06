from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import Books
from pgvector.django import CosineDistance
from django.db.models import F, Q, Value, ExpressionWrapper, FloatField
from django.db.models.functions import Concat, Cast
from rank_bm25 import BM25Okapi
from django.conf import settings

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


def prepare_bm25_corpus():
    books = Books.objects.values('id', 'title', 'summary')
    corpus = []
    book_data = []

    for book in books:
        # Kết hợp title và summary thành một đoạn văn bản
        content = (book['title'] or '') + " " + (book['summary'] or '')
        tokens = content.lower().split()
        corpus.append(tokens)
        book_data.append(book)
    
    bm25 = BM25Okapi(corpus)
    return bm25, book_data


@csrf_exempt
def get_book_suggestions(request, top_n=3):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message', '')

        if message is None:
            return JsonResponse({'error': 'Invalid message'}, status=400)
        
        # Sử dụng phương pháp BM25
        bm25, book_data = prepare_bm25_corpus()
        query_tokens = message.lower().split()
        bm25_scores = bm25.get_scores(query_tokens)
        

        message_embedding = encode_message(message)

        if message_embedding is None:
            return JsonResponse({'error': 'Invalid message embedding'}, status=400)
        
        top_similarity = 10

        # Sử dụng tìm kiếm sách tương đồng với message
        similar_books = Books.objects.annotate(
            summary_similarity=CosineDistance(F('summary_embed'), message_embedding),
            title_similarity=CosineDistance(F('title_embed'), message_embedding),
        ).annotate(
            combined_similarity=Cast(
                (0.5 * F('title_similarity') + 0.75 * F('summary_similarity')), 
                FloatField()
            )
        ).order_by('combined_similarity')[:top_similarity]


        # similar_books = Books.objects.annotate(
        #     combined_text=encode_message(Concat(F('title'), Value(' '), F('summary'))),  # Kết hợp title và summary
        #     combined_similarity=CosineDistance(F('combined_text'), message_embedding)  # Tính độ tương đồng cho chuỗi kết hợp
        # ).order_by('combined_similarity')[:top_similarity]
        suggestions = []

        for book in similar_books:
            bm25_score = 0
            for index, book_info in enumerate(book_data):
                if book_info['id'] == book.id:
                    bm25_score = bm25_scores[index]
                    break

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

            combined_similarity = (
                book.combined_similarity 
                if book.combined_similarity is not None and not math.isnan(book.combined_similarity) 
                else 'No combined similarity available'
            )

            image_url = (
                f"{settings.MEDIA_URL}{settings.MEDIA_IMAGE_PATH}/{book.image}"
                if book.image
                else None
            )
            
            suggestions.append({
                'id': book.id,
                'title': book.title,
                'summary': summary,
                'image': image_url,
                'author': book.author,
                'published_date': book.published_date,
                'created_date': book.created_date,
                'modified_date': book.modified_date,
                'summary_similarity': summary_similarity,
                'title_similarity': title_similarity,
                'combined_similarity': combined_similarity,
                'bm25_score': bm25_score,
            })

        top_n = top_n
        suggestions = sorted(suggestions, key=lambda x: x['bm25_score'], reverse=True)[:top_n]

        # Trả về danh sách sách tương đồng và message ban đầu
        response_data = {
            'message': message,
            'suggestions': suggestions,
        }

        return JsonResponse(response_data, safe=False)
    return JsonResponse({'error': 'Invalid request method'}, status=400)




def get_book_suggestions_from_query(query, top_n=5):
    """
    Hàm tìm kiếm sách gợi ý từ query, trả về kết quả giống get_book_suggestions
    """
    # Sử dụng phương pháp BM25 hoặc bất kỳ phương pháp tìm kiếm nào bạn đã sử dụng
    bm25, book_data = prepare_bm25_corpus()
    query_tokens = query.lower().split()
    bm25_scores = bm25.get_scores(query_tokens)

    # Tạo embedding cho query message
    message_embedding = encode_message(query)

    if message_embedding is None:
        return {'error': 'Invalid message embedding'}

    top_similarity = 10
    # Tìm kiếm sách tương đồng với message
    similar_books = Books.objects.annotate(
        summary_similarity=CosineDistance(F('summary_embed'), message_embedding),
        title_similarity=CosineDistance(F('title_embed'), message_embedding),
    ).annotate(
        combined_similarity=Cast(
            (0.5 * F('title_similarity') + 0.75 * F('summary_similarity')),
            FloatField()
        )
    ).order_by('combined_similarity')[:top_similarity]

    suggestions = []
    for book in similar_books:
        bm25_score = 0
        for index, book_info in enumerate(book_data):
            if book_info['id'] == book.id:
                bm25_score = bm25_scores[index]
                break

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

        combined_similarity = (
            book.combined_similarity 
            if book.combined_similarity is not None and not math.isnan(book.combined_similarity) 
            else 'No combined similarity available'
        )

        image_url = (
            f"{settings.MEDIA_URL}{settings.MEDIA_IMAGE_PATH}/{book.image}"
            if book.image
            else None
        )
        
        suggestions.append({
            'id': book.id,
            'title': book.title,
            'summary': summary,
            'image': image_url,
            'author': book.author,
            'published_date': book.published_date,
            'created_date': book.created_date,
            'modified_date': book.modified_date,
            'summary_similarity': summary_similarity,
            'title_similarity': title_similarity,
            'combined_similarity': combined_similarity,
            'bm25_score': bm25_score,
        })
    suggestions = sorted(suggestions, key=lambda x: x['bm25_score'], reverse=True)[:top_n]
    # Trả về kết quả gợi ý
    return {'suggestions': suggestions}