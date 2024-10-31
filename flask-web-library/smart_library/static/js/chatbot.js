function openChatbot() {
    document.getElementById("chatbot-panel").style.transform = "translateX(0%)";
    document.getElementById("chatbot-toggle-btn").style.display = "none";
}

function closeChatbot() {
    document.getElementById("chatbot-panel").style.transform = "translateX(100%)";
    document.getElementById("chatbot-toggle-btn").style.display = "block";
}

async function fetchBookSuggestions(userInput) {
    const response = await fetch('http://localhost:1111/get_book_suggestions/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userInput }),
    });

    if (!response.ok) {
        throw new Error('Failed to fetch book suggestions');
    }

    return response.json();
}

async function sendPromptToChatbot(userInput, suggestions) {
    const response = await fetch('https://zep.hcmute.fit/7561/send_prompt', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: userInput,
            suggestions: suggestions,
        }),
    });

    if (!response.ok) {
        throw new Error('Failed to send prompt to chatbot');
    }

    return response.body.getReader(); // Trả về reader để xử lý stream
}

function readStream(reader) {
    const decoder = new TextDecoder('utf-8');
    const chatResponse = document.getElementById('chatbot-response');

    function processChunk() {
        reader.read().then(({ done, value }) => {
            if (done) {
                console.log('Stream finished.');
                return;
            }

            const chunk = decoder.decode(value, { stream: true });
            chatResponse.innerHTML += chunk; 

            // Gọi lại hàm để đọc tiếp
            processChunk();
        });
    }

    processChunk(); // Bắt đầu đọc stream
}


async function sendMessage() {
    const userInput = document.getElementById('user-input').value;

    try {
        // Gọi API lấy gợi ý sách
        const data = await fetchBookSuggestions(userInput);
        console.log('Book Suggestions:', data)
        
        // Gọi API gửi prompt cho chatbot

        const reader = await sendPromptToChatbot(userInput, data.suggestions);
        console.log('Prompt Suggestions:', reader)
        // Xử lý phản hồi từ stream
        readStream(reader);
    } catch (error) {
        console.error('Error:', error);
    }
}