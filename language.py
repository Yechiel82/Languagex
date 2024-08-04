
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>StudyDoc Generator</title>
#     <style>
#       :root {
#           --background-color: #f7f7f9;
#           --sidebar-color: #ffffff;
#           --text-color: #333333;
#           --accent-color: #f36;
#           --border-color: #e0e0e0;
#       }

#       body {
#           font-family: 'Arial', sans-serif;
#           line-height: 1.6;
#           background-color: var(--background-color);
#           color: var(--text-color);
#           margin: 0;
#           padding: 0;
#           display: flex;
#       }

#       .sidebar {
#           width: 250px;
#           background-color: var(--sidebar-color);
#           padding: 20px;
#           height: 100vh;
#           border-right: 1px solid var(--border-color);
#       }

#       .main-content {
#           flex: 1;
#           padding: 20px;
#           max-width: 800px;
#           margin: 0 auto;
#       }

#       .logo {
#           font-size: 24px;
#           font-weight: bold;
#           margin-bottom: 20px;
#           display: flex;
#           align-items: center;
#       }

#       .logo-icon {
#           background-color: #000;
#           color: #fff;
#           width: 30px;
#           height: 30px;
#           display: flex;
#           align-items: center;
#           justify-content: center;
#           border-radius: 8px;
#           margin-right: 10px;
#       }

#       .new-chat {
#           background-color: #fff;
#           border: 1px solid var(--border-color);
#           border-radius: 20px;
#           padding: 10px 15px;
#           margin-bottom: 20px;
#           cursor: pointer;
#       }

#       h2 {
#           font-size: 14px;
#           color: #888;
#           margin-bottom: 10px;
#       }

#       .chat-history {
#           list-style-type: none;
#           padding: 0;
#       }

#       .chat-history li {
#           margin-bottom: 10px;
#           cursor: pointer;
#       }

#       .input-area {
#           position: fixed;
#           bottom: 20px;
#           left: 270px;
#           right: 20px;
#           display: flex;
#           align-items: center;
#       }

#       #userInput {
#           flex: 1;
#           padding: 10px 15px;
#           border: 1px solid var(--border-color);
#           border-radius: 20px;
#           font-size: 16px;
#       }

#       .send-button {
#           background-color: var(--accent-color);
#           color: white;
#           border: none;
#           border-radius: 50%;
#           width: 40px;
#           height: 40px;
#           margin-left: 10px;
#           cursor: pointer;
#           display: flex;
#           align-items: center;
#           justify-content: center;
#       }

#       .message {
#           background-color: #fff;
#           border-radius: 10px;
#           padding: 15px;
#           margin-bottom: 20px;
#       }

#       .user-message {
#           background-color: #f0f0f0;
#       }

#       .ai-message {
#           background-color: #fff;
#       }

#       .ai-icon {
#           background-color: #000;
#           color: #fff;
#           width: 30px;
#           height: 30px;
#           display: inline-flex;
#           align-items: center;
#           justify-content: center;
#           border-radius: 8px;
#           margin-right: 10px;
#       }
#   </style>
# </head>
# <body>
#     <div class="sidebar">
#         <div class="logo">
#             <span class="logo-icon">"</span>
#             StudyDoc
#         </div>
#         <div class="new-chat">+ New Chat</div>
#         <h2>This Month (July)</h2>
#         <ul class="chat-history">
#             <li>How can I create a visualization...</li>
#             <li>What software or tools do...</li>
#             <li>Can you provide tips for...</li>
#         </ul>
#     </div>

#     <div class="main-content">
#         <div id="chatContent"></div>
#     </div>

#     <div class="input-area">
#         <input type="text" id="userInput" placeholder="Send a new message">
#         <button class="send-button" onclick="sendMessage()">➤</button>
#     </div>

#     <script>
#         function sendMessage() {
#             const userInput = document.getElementById('userInput');
#             const chatContent = document.getElementById('chatContent');
            
#             // Add user message
#             const userMessage = document.createElement('div');
#             userMessage.className = 'message user-message';
#             userMessage.textContent = userInput.value;
#             chatContent.appendChild(userMessage);
            
#             // Create FormData object
#             const formData = new FormData();
#             formData.append('message', userInput.value);
            
#             // Send request to the server
#             fetch('/generate', {
#                 method: 'POST',
#                 body: formData,
#             })
#             .then(response => response.json())
#             .then(data => {
#                 const aiMessage = document.createElement('div');
#                 aiMessage.className = 'message ai-message';
#                 if (data.success) {
#                     aiMessage.innerHTML = '<span class="ai-icon">"</span><pre>' + data.content + '</pre>';
#                 } else {
#                     aiMessage.innerHTML = '<span class="ai-icon">"</span><p>Error: ' + data.error + '</p>';
#                 }
#                 chatContent.appendChild(aiMessage);
#             })
#             .catch(error => {
#                 console.error('Error:', error);
#                 const errorMessage = document.createElement('div');
#                 errorMessage.className = 'message ai-message';
#                 errorMessage.innerHTML = '<span class="ai-icon">"</span><p>An error occurred. Please try again.</p>';
#                 chatContent.appendChild(errorMessage);
#             });
            
#             userInput.value = '';
#         }

#         // Add event listener for Enter key in the input field
#         document.getElementById('userInput').addEventListener('keypress', function(e) {
#             if (e.key === 'Enter') {
#                 sendMessage();
#             }
#         });
#     </script>
# </body>
# </html>