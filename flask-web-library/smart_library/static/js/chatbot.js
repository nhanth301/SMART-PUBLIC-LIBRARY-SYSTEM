const chatbotPanel = document.getElementById('chatbot-panel');
const chatbotToggleBtn = document.getElementById('chatbot-toggle-btn');


function openChatbot() {
    chatbotPanel.style.transform = 'translateX(0)';
    chatbotToggleBtn.style.display = "none";
}

function closeChatbot() {
    chatbotPanel.style.transform = 'translateX(100%)';
    chatbotToggleBtn.style.display = "block";
}

async function fetchBookSuggestions(userInput) {
    try {
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
    } catch (error) {
        console.error('Error fetching book suggestions:', error);
        throw error;
    }
}

async function sendPromptToChatbot(userInput, suggestions) {
    try {
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
    } catch (error) {
        console.error('Error sending prompt to chatbot:', error);
        throw error;
    }
}

function formatTextWithMarkdown(text) {
    // Thay thế ** bằng <b> cho in đậm
    text = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>'); 
    // Thay thế * bằng <i> cho in nghiêng
    text = text.replace(/\*(.*?)\*/g, '<i>$1</i>'); 
    // Thêm các xử lý khác nếu cần (vd: thay thế newline, các ký tự đặc biệt khác)
    text = text.replace(/\n/g, '<br>'); // Xử lý xuống dòng
    text = text.split(/- /).map((segment, index) => {
        if (index === 0) {
            // Đoạn đầu tiên không có dấu "-"
            return segment;
        }
        return `<p>- ${segment.trim()}</p>`;
    }).join(''); 

    text = text.replace(/\[(\d+)\]/g, function(match, bookId) {
        // Tạo sự kiện onclick cho bookId
        return `<span class="book-id" onclick="openDialog(${bookId})" style="color:blue">${match}</span>`;
    });

    return text;
}

function readStream(reader) {
    const decoder = new TextDecoder('utf-8');
    const chatResponse = document.getElementById('chatbot-response');

    const botMessage = document.createElement('div');
    botMessage.classList.add('message', 'bot');
    chatResponse.appendChild(botMessage);
    chatResponse.scrollTop = chatResponse.scrollHeight;

    let fullMessage = '';


    function processChunk() {
        reader.read().then(({ done, value }) => {
            if (done) {
                console.log('Stream finished.');
                chatResponse.scrollTop = chatResponse.scrollHeight;
                return;
            }

            const chunk = decoder.decode(value, { stream: true });
            // chatResponse.innerHTML += chunk;

            if (chunk.trim()) {
                // Ghép chunk vào thông điệp đầy đủ
                fullMessage += chunk;

                // Xử lý và cập nhật nội dung trong thời gian thực
                const formattedMessage = formatTextWithMarkdown(fullMessage.trim());
                botMessage.innerHTML = formattedMessage; // Cập nhật nội dung
            }

            // const formattedMessage = formatTextWithMarkdown(fullMessage.trim());

            // botMessage.innerHTML = formattedMessage;

            // Cuộn xuống cuối
            chatResponse.scrollTop = chatResponse.scrollHeight;
            
            processChunk();
        }).catch(error => {
            console.error('Error while reading stream:', error);

            // Hiển thị thông báo lỗi trong đoạn tin nhắn
            botMessage.textContent = 'Đã xảy ra lỗi khi nhận dữ liệu.';
        });
    }

    processChunk(); // Bắt đầu đọc stream
}

async function sendMessage() {
    const userInputElement = document.getElementById('user-input');
    const userInput = userInputElement.value.trim();
    const chatResponse = document.getElementById('chatbot-response');

    if (!userInput) {
        console.warn('User input is empty.');
        return;
    }

    // Hiển thị tin nhắn của người dùng
    const userMessage = document.createElement('div');
    userMessage.classList.add('message', 'user');
    userMessage.textContent = userInput;
    chatResponse.appendChild(userMessage);
    userInputElement.value = '';

    // Cuộn xuống cuối
    chatResponse.scrollTop = chatResponse.scrollHeight;

    // const botResponse = '\n    \n\nHere are some books you might find interesting based on your input:\n **Python Programming An Introduction to Computer Science [76]**\n     This book covers fundamental concepts of Python programming and computer science, including syntax, control structures, object-oriented programming, algorithms, basic data structures, and problem-solving.\n\n    **Python Data Analytics Data Analysis and Science Using Pandas, matplotlib, and the Python Programming Language [37]**\n        This book focuses on teaching data analysis and data science using Python, with a strong emphasis on the Pandas and Matplotlib libraries for handling and visualizing data. It covers topics like data manipulation, visualization techniques, basic statistical analysis, and real-world data examples.\n\n    **Python and Tkinter Programming [77]**\n       This book provides full documentation for the Tkinter library and includes numerous examples of real-world Python/Tkinter applications. It serves as a resource for learning how to create graphical user interfaces (GUIs) using Python. \n    **Hands-On Machine Learning with Scikit-Learn and TensorFlow: Concepts, Tools, and Techniques to Build Intelligent Systems [103]**\n      This book provides a practical guide to machine learning using Python frameworks like scikit-learn and TensorFlow. It covers'
    // const formattedResponse = formatTextWithMarkdown(botResponse);

    // const botMessage = document.createElement('div');
    // botMessage.classList.add('message', 'bot');
    // botMessage.innerHTML = formattedResponse;

    // chatResponse.appendChild(botMessage);
    // // Cuộn xuống cuối sau khi thêm tin nhắn bot
    // chatResponse.scrollTop = chatResponse.scrollHeight;

    try {
        // Gọi API lấy gợi ý sách
        const suggestionsData = await fetchBookSuggestions(userInput);

        if (!suggestionsData || !suggestionsData.suggestions) {
            throw new Error('No suggestions found.');
        }

        // Gọi API chatbot với gợi ý sách
        const reader = await sendPromptToChatbot(userInput, suggestionsData.suggestions);

        // Xử lý phản hồi từ stream
        readStream(reader);
    } catch (error) {
        console.error('Error during message processing:', error);
        const errorMessage = document.createElement('div');
        errorMessage.classList.add('message', 'bot');
        errorMessage.textContent = 'Đã xảy ra lỗi, vui lòng thử lại sau.';
        chatResponse.appendChild(errorMessage);
    }finally {
        // Cuộn xuống cuối
        chatResponse.scrollTop = chatResponse.scrollHeight;
    }
}

// async function sendMessage() {
//     const userInput = document.getElementById('user-input').value;

//     try {
//         // Gọi API lấy gợi ý sách
//         const data = await fetchBookSuggestions(userInput);
//         console.log('Book Suggestions:', data)
        
//         // Gọi API gửi prompt cho chatbot

//         const reader = await sendPromptToChatbot(userInput, data.suggestions);
//         console.log('Prompt Suggestions:', reader)
//         // Xử lý phản hồi từ stream
//         readStream(reader);
//     } catch (error) {
//         console.error('Error:', error);
//     }
// }