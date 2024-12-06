from django.test import TestCase
from .chatbot_logic import encode_message
from django.urls import reverse
from rest_framework import status

class BookSuggestionTests(TestCase):

    def test_encode_message(self):
        message = "Một cuốn sách thú vị"
        embedding = encode_message(message)
        self.assertIsNotNone(embedding)  

    # def test_get_book_suggestions(self):
    #     url = reverse('get_book_suggestions')  
    #     data = {'message': 'Tìm một cuốn sách hay'}

    #     response = self.client.post(url, data, content_type='application/json')
        
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)  # Kiểm tra mã trạng thái
    #     self.assertIn('suggestions', response.json())  # Kiểm tra xem có key suggestions trong phản hồi
