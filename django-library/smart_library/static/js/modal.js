// Mở modal và lấy thông tin sách
const dialog = document.querySelector("dialog");


function openDialog(bookId) {
    // Gọi API để lấy chi tiết sách
    handleClick(bookId, 'click')

    fetch(`/api/books/${bookId}/`)
        .then(response => response.json())
        .then(data => {
            // Cập nhật nội dung của modal với thông tin sách
            document.getElementById('bookTitle').textContent = data.title;
            document.getElementById('bookAuthor').textContent = 'Author: ' + data.author;
            document.getElementById('bookSummary').innerHTML = `<p style="font-size: 20px; font-weight:bold">Summary:</p><span style="font-style: italic;">${data.summary}</span>`;
            const viewPDFLink = document.getElementById('viewPDFLink');
            viewPDFLink.href = `http://localhost:8083/read/${data.id}/pdf`; 
            viewPDFLink.onclick = function() {
                handleClick(data.id, 'read');
            };

            document.getElementById('bookImageDialog').src = data.image;
            


            const tagsContainer = document.getElementById('bookTags');
            tagsContainer.textContent = ''; // Xóa nội dung cũ nếu có
            if (data.tags && data.tags.length > 0) {
                data.tags.forEach(tag => {
                    const tagLink = document.createElement('a');
                    tagLink.href = `/search?query=${encodeURIComponent(tag)}&search_type=tags`;
                    tagLink.textContent = tag;
                    tagLink.style.marginRight = '8px'; // Thêm khoảng cách giữa các thẻ
                    tagLink.style.textDecoration = 'none'; // Tùy chỉnh giao diện nếu cần
                    tagLink.style.color = 'white'; // Đặt màu liên kết
                    tagLink.style.borderRadius = '3px';
                    tagLink.style.backgroundColor= '#007bff';
                    tagLink.style.minHeight='5px';
                    tagLink.style.padding='4px';
                    tagsContainer.appendChild(tagLink);
                });
            }

            // Hiển thị modal
            
            dialog.showModal()

        })
        .catch(error => {
            console.error('Error fetching book details:', error);
        });

}

// Đóng modal
function closeDialog() {
    dialog.close()
}

// Thêm sự kiện để đóng modal khi người dùng click bên ngoài modal
dialog.addEventListener('click', function (event) {
    const dialogBounds = dialog.getBoundingClientRect();
    if (
        event.clientX < dialogBounds.left ||
        event.clientX > dialogBounds.right ||
        event.clientY < dialogBounds.top ||
        event.clientY > dialogBounds.bottom
    ) {
        closeDialog();
    }
});

